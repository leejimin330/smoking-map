// 지도 어댑터 — 오픈스트리트맵(Leaflet). 카카오 키가 생기면 같은 모양의 map-kakao.js로 바꾼다.
// 화면 코드(app.js)는 아래 createMap이 돌려주는 메서드만 쓴다.
/* global L */

const SEOUL = [37.5665, 126.978];

export function createMap(el, { onSelect }) {
  const map = L.map(el, { zoomControl: false, attributionControl: true }).setView(SEOUL, 12);
  L.control.zoom({ position: "topright" }).addTo(map);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(map);

  const cluster = L.markerClusterGroup({ maxClusterRadius: 42, disableClusteringAtZoom: 16, showCoverageOnHover: false });
  map.addLayer(cluster);
  const markers = new Map();
  let selectedId = null;
  let meMarker = null;

  const icon = (p, selected) => L.divIcon({
    className: "",
    html: `<div class="pin${p.approx ? " approx" : ""}${selected ? " selected" : ""}" style="--c: var(--${p.kind})"></div>`,
    iconSize: selected ? [24, 24] : [18, 18],
    iconAnchor: selected ? [12, 12] : [9, 9],
  });

  return {
    setPlaces(places) {
      cluster.clearLayers();
      markers.clear();
      for (const p of places) {
        const m = L.marker([p.lat, p.lng], { icon: icon(p, p.id === selectedId), title: p.name, keyboard: true });
        m.on("click", () => onSelect(p));
        markers.set(p.id, { marker: m, place: p });
        cluster.addLayer(m);
      }
    },
    select(place) {
      if (selectedId && markers.has(selectedId)) {
        const prev = markers.get(selectedId);
        prev.marker.setIcon(icon(prev.place, false));
      }
      selectedId = place?.id ?? null;
      if (place && markers.has(place.id)) {
        const cur = markers.get(place.id);
        cur.marker.setIcon(icon(place, true));
        cluster.zoomToShowLayer(cur.marker, () => map.panTo([place.lat, place.lng]));
      }
    },
    showMe(here) {
      const ll = [here.lat, here.lng];
      if (meMarker) meMarker.setLatLng(ll);
      else meMarker = L.marker(ll, { icon: L.divIcon({ className: "", html: '<div class="me"></div>', iconSize: [16, 16], iconAnchor: [8, 8] }), zIndexOffset: 1000, interactive: false }).addTo(map);
    },
    fit(points) {
      if (!points.length) return;
      map.fitBounds(L.latLngBounds(points.map((p) => [p.lat, p.lng])), { padding: [48, 48], maxZoom: 17 });
    },
    resize() { map.invalidateSize(); },
  };
}
