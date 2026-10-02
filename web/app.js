import { directionsUrl, distanceMeters, formatDistance, nearest, walkMinutes } from "./geo.js";
import { createMap } from "./map-leaflet.js";

const KINDS = {
  closed: "폐쇄형 부스",
  partial: "부분 개방형",
  open: "완전 개방형",
  indoor: "건물 안 흡연실",
};
const KIND_HELP = {
  closed: "벽과 문으로 막힌 부스예요.",
  partial: "지붕이나 칸막이가 일부 있는 곳이에요.",
  open: "선만 그어진 열린 공간이에요.",
  indoor: "건물 안 흡연실이라 그 건물 이용자만 쓸 수 있을 수 있어요.",
};
const NEAREST_COUNT = 5;
const STORE = "smoking-map:kinds";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

let places = [];
let sources = [];
let here = null;                     // 내 위치 {lat,lng}
let kinds = loadKinds();
let view = { mode: "home" };         // home | nearby | place

const map = createMap($("map"), { onSelect: (p) => show({ mode: "place", place: p }) });

function loadKinds() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORE) || "null");
    if (Array.isArray(saved) && saved.length) return new Set(saved.filter((k) => k in KINDS));
  } catch { /* 저장소를 못 써도 기본값으로 */ }
  return new Set(["closed", "partial", "open"]);   // 건물 안 흡연실은 기본으로 숨긴다
}
function saveKinds() { try { localStorage.setItem(STORE, JSON.stringify([...kinds])); } catch { /* 무시 */ } }

const visible = () => places.filter((p) => kinds.has(p.kind));

function renderChips() {
  const counts = Object.fromEntries(Object.keys(KINDS).map((k) => [k, places.filter((p) => p.kind === k).length]));
  $("chips").innerHTML = Object.entries(KINDS).map(([k, label]) =>
    `<button class="chip" type="button" data-kind="${k}" aria-pressed="${kinds.has(k)}" style="--c: var(--${k})" title="${esc(KIND_HELP[k])}">
       <span class="sw" aria-hidden="true"></span>${label}<span class="n">${counts[k]}</span></button>`).join("");
}
$("chips").addEventListener("click", (e) => {
  const b = e.target.closest("[data-kind]");
  if (!b) return;
  const k = b.dataset.kind;
  kinds.has(k) ? kinds.delete(k) : kinds.add(k);
  if (!kinds.size) kinds.add(k);   // 하나는 남긴다
  saveKinds();
  renderChips();
  map.setPlaces(visible());
  show(view.mode === "place" ? view : view.mode === "nearby" ? { mode: "nearby" } : { mode: "home" });
});

function kindTag(k) { return `<span class="kind" style="--c: var(--${k})">${KINDS[k]}</span>`; }

function show(next) {
  view = next;
  const panel = $("panel");
  if (view.mode === "place") {
    const p = view.place;
    map.select(p);
    const d = here ? distanceMeters(here, p) : null;
    panel.innerHTML = `
      <div class="row">${kindTag(p.kind)}${d !== null ? `<span class="muted">${formatDistance(d)} · 걸어서 ${walkMinutes(d)}분</span>` : ""}</div>
      <h2>${esc(p.name)}</h2>
      ${p.address ? `<p class="muted">${esc(p.address)}</p>` : ""}
      ${p.detail ? `<p class="muted">${esc(p.detail)}</p>` : ""}
      ${p.approx ? `<p class="note">주소로 찾은 대략적인 위치예요. 근처에서 안내판을 확인하세요.</p>` : ""}
      <p class="muted">${esc(KIND_HELP[p.kind])}</p>
      <div class="row">
        <a class="primary" href="${directionsUrl(p)}" target="_blank" rel="noreferrer">카카오맵 길찾기</a>
        <button class="secondary" type="button" id="back">${here ? "가까운 곳 목록" : "처음으로"}</button>
      </div>
      <p class="small">출처: ${p.sources.map((s) => esc(sources.find((x) => x.key === s)?.title ?? s)).join(", ")}</p>`;
    $("back").addEventListener("click", () => { map.select(null); show(here ? { mode: "nearby" } : { mode: "home" }); });
    return;
  }
  map.select(null);
  if (view.mode === "nearby" && here) {
    const list = nearest(places, here, NEAREST_COUNT, kinds);
    const closest = list[0];
    panel.innerHTML = `
      <h2>내 주변 흡연구역</h2>
      ${closest && closest.meters > 3000 ? `<p class="note">가장 가까운 곳도 ${formatDistance(closest.meters)} 떨어져 있어요. 아직 서울 일부 구 자료만 있어요.</p>` : ""}
      <ol class="list">${list.map((x, i) => `
        <li><button type="button" data-id="${x.place.id}">
          <span class="rank">${i + 1}</span>
          <span class="name">${esc(x.place.name)}<span class="sub">${KINDS[x.place.kind]} · ${esc(x.place.gu)}</span></span>
          <span class="dist">${formatDistance(x.meters)}<small>${walkMinutes(x.meters)}분</small></span>
        </button></li>`).join("")}</ol>`;
    panel.querySelector(".list").addEventListener("click", (e) => {
      const b = e.target.closest("[data-id]");
      if (b) show({ mode: "place", place: places.find((p) => p.id === b.dataset.id) });
    });
    return;
  }
  const gus = new Set(places.map((p) => p.gu));
  panel.innerHTML = `
    <p class="muted">서울 공공 흡연구역 <b>${places.length}곳</b>(${gus.size}개 구)을 지도에 모았어요.
      <b>내 주변</b>을 누르면 가장 가까운 ${NEAREST_COUNT}곳과 걸어서 걸리는 시간을 보여 드려요.</p>
    <button class="primary" type="button" id="find">내 주변 흡연구역 찾기</button>
    <p class="small">점선 테두리 표시는 주소로 찾은 대략적인 위치예요.</p>`;
  $("find").addEventListener("click", locate);
}

function locate() {
  const btn = $("locate");
  if (!navigator.geolocation) return locateFailed("이 브라우저는 위치 기능을 지원하지 않아요.");
  btn.disabled = true;
  navigator.geolocation.getCurrentPosition((pos) => {
    btn.disabled = false;
    here = { lat: pos.coords.latitude, lng: pos.coords.longitude };
    map.showMe(here);
    const list = nearest(places, here, NEAREST_COUNT, kinds);
    map.fit([here, ...list.slice(0, 3).map((x) => x.place)]);
    show({ mode: "nearby" });
  }, (err) => {
    btn.disabled = false;
    locateFailed(err.code === err.PERMISSION_DENIED
      ? "위치 권한이 꺼져 있어요. 브라우저 주소창의 자물쇠 아이콘에서 위치를 허용하거나, 지도를 움직여 직접 찾아 주세요."
      : "위치를 확인하지 못했어요. 잠시 뒤 다시 눌러 주세요.");
  }, { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 });
}
function locateFailed(message) {
  show({ mode: "home" });
  $("panel").insertAdjacentHTML("afterbegin", `<p class="note" role="alert">${esc(message)}</p>`);
}
$("locate").addEventListener("click", locate);

// 자료 출처
$("about-open").addEventListener("click", () => $("about").showModal());
$("about-close").addEventListener("click", () => $("about").close());
$("about").addEventListener("click", (e) => { if (e.target === $("about")) $("about").close(); });

async function start() {
  try {
    const data = await (await fetch("data/places.json", { cache: "no-cache" })).json();
    places = data.places;
    sources = data.sources;
    $("source-list").innerHTML = sources.filter((s) => s.count).map((s) =>
      `<li><a href="${esc(s.url)}" target="_blank" rel="noreferrer">${esc(s.fileTitle || s.title)}</a> (${s.count}건)</li>`).join("");
    $("generated").textContent = `자료를 모은 날: ${data.generatedAt.slice(0, 10)}`;
  } catch {
    $("panel").innerHTML = `<p class="note" role="alert">흡연구역 자료를 불러오지 못했어요. 새로고침해 주세요.</p>`;
    return;
  }
  renderChips();
  map.setPlaces(visible());
  show({ mode: "home" });
}
window.addEventListener("resize", () => map.resize());
start();
