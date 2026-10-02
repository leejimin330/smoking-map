"""서울 흡연구역 자료를 모아 하나의 JSON으로 만든다.

    python scripts/build.py            # data/raw/* → web/data/places.json

- 원자료: 서울시 통합(실외 공공 흡연시설) + 구별 흡연시설 파일(data/raw, scripts/fetch.py가 받는다).
- 좌표가 없는 곳은 주소로 좌표를 찾는다. 찾은 결과는 data/geocode-cache.json에 남겨 다시 묻지 않는다.
- 끝까지 못 찾은 곳은 data/unplaced.csv로 남긴다. data/manual-coords.csv에 좌표를 적으면 다음 빌드에 들어간다.
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CACHE = ROOT / "data" / "geocode-cache.json"
MANUAL = ROOT / "data" / "manual-coords.csv"
UNPLACED = ROOT / "data" / "unplaced.csv"
OUT = ROOT / "web" / "data" / "places.json"

SEOUL_GU = ("종로구 중구 용산구 성동구 광진구 동대문구 중랑구 성북구 강북구 도봉구 노원구 은평구 서대문구 마포구 "
            "양천구 강서구 구로구 금천구 영등포구 동작구 관악구 서초구 강남구 송파구 강동구").split()

MERGE_METERS = 30  # 이보다 가까우면 같은 흡연구역으로 본다


@dataclass
class Place:
    name: str
    address: str | None
    gu: str
    kind: str                     # closed | partial | open | indoor
    source: str
    lat: float | None = None
    lng: float | None = None
    approx: bool = False          # 좌표가 건물이 아니라 동네 수준으로 잡힘
    detail: str = ""
    sources: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.sources:
            self.sources = [self.source]


# ---- 정규화 ----
def normalize_kind(text: str | None) -> str:
    """자료마다 다른 시설 형태 표기를 closed/partial/open 세 가지로."""
    t = re.sub(r"\s+", "", text or "")
    if "부분" in t:
        return "partial"
    if "폐쇄" in t:
        return "closed"
    if "개방" in t:
        return "open"
    return "partial"


ROAD = re.compile(r"([가-힣0-9]+(?:대로|로|길))\s*(\d+)\s*(길)?\s*(\d+(?:-\d+)?)?")
JIBUN = re.compile(r"([가-힣0-9]+(?:동|가))\s+(\d+(?:-\d+)?)")


def extract_address(text: str | None, gu: str) -> str | None:
    """설명 글("교보타워(강남대로 465) 부지 옆")에서 도로명·지번 주소를 뽑아 '서울특별시 ○○구 …'로."""
    if not text:
        return None
    t = re.sub(r"\s+", " ", text).strip()
    # 지번을 먼저: "남대문로5가 520"을 도로명 "남대문로 5"로 잘못 읽지 않게
    m = JIBUN.search(t)
    if m:
        return f"서울특별시 {gu} {m.group(1)} {m.group(2)}"
    m = ROAD.search(t)
    if m:
        road, num, gil, num2 = m.groups()
        # "법원로 11길 11" → "법원로11길 11"
        addr = f"{road}{num}길 {num2}" if gil and num2 else f"{road} {num}"
        return f"서울특별시 {gu} {addr}"
    return None


def clean_address(text: str) -> str:
    """주소 뒤에 붙은 '번지', 층수, 괄호 속 동 이름을 뗀다 — 주소 검색이 이것 때문에 못 찾는다."""
    t = re.sub(r"\(.*?\)", "", text or "")
    t = re.sub(r"번지.*$", "", t)
    t = re.sub(r"\s+(지하|지상)?\s*[\d,]+층.*$", "", t)
    return re.sub(r"\s+", " ", t).strip()


def clean(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def gu_of(text: str, default: str = "") -> str:
    for g in SEOUL_GU:
        if g in (text or ""):
            return g
    return default


# ---- 원자료 읽기: 자료마다 칸 이름이 달라 하나씩 맞춘다 ----
def read_csv(name: str) -> list[dict]:
    raw = (RAW / name).read_bytes()
    for enc in ("utf-8-sig", "cp949"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    return [{k.strip(): clean(v) for k, v in row.items() if k} for row in csv.DictReader(io.StringIO(text))]


def num(text) -> float | None:
    try:
        v = float(str(text).strip())
        return v if v else None
    except (TypeError, ValueError):
        return None


def from_seoul() -> list[Place]:
    import openpyxl
    ws = openpyxl.load_workbook(RAW / "seoul.xlsx", read_only=True).worksheets[0]
    out = []
    for row in ws.iter_rows(values_only=True):
        if not isinstance(row[0], int):
            continue
        _, host, where, addr, kind, _count = row[:6]
        gu = gu_of(clean(addr)) or gu_of(clean(host))
        out.append(Place(name=clean(where), address=extract_address(addr, gu) or clean(addr), gu=gu,
                         kind=normalize_kind(kind), source="seoul", detail=f"설치: {clean(host)}"))
    return out


def from_gwanak():
    return [Place(name=r["상세위치"], address=r["위치"].replace("관악구 관악구", "관악구"), gu="관악구",
                  kind=normalize_kind(r["구분"]), source="gwanak", detail=f"관리: {r['운영관리']}")
            for r in read_csv("gwanak.csv") if r.get("위치")]


def from_jongno():
    return [Place(name=r["설 치 위 치"], address=extract_address(r["설 치 위 치"], "종로구"), gu="종로구",
                  kind=normalize_kind(r["형 태"]), source="jongno", detail=f"{r['운영여부']} · 관리: {r['부스 관리 기관명']}")
            for r in read_csv("jongno.csv") if "운영" in r.get("운영여부", "운영")]


def from_junggu():
    return [Place(name=r["설치위치"], address=r["설치도로명주소"], gu="중구", kind=normalize_kind(r["구분"]),
                  source="junggu", detail=f"관리: {r['운영관리']}") for r in read_csv("junggu.csv")]


def from_jungnang():
    # 공중이용시설 안의 흡연실 — 그 건물을 이용하는 사람만 쓸 수 있는 곳이 많다
    return [Place(name=r["시설명(업소)"], address=clean_address(r["주소"]), gu="중랑구", kind="indoor",
                  source="jungnang", detail=f"{r['업종']} 건물 안 흡연실 {r['흡연실 개소수']}곳") for r in read_csv("jungnang.csv")]


def from_seocho():
    return [Place(name=r["설치위치"], address=extract_address(r["설치위치"], "서초구"), gu="서초구",
                  kind=normalize_kind(r["시설형태"]), source="seocho", detail=f"{r['해당동']} · 관리: {r['청소관리']}")
            for r in read_csv("seocho.csv")]


def from_seodaemun():
    return [Place(name=f"{r['설치위치']} {r['설치위치 상세']}".strip(), address=extract_address(r["설치위치"], "서대문구"),
                  gu="서대문구", kind=normalize_kind(r["시설형태"]), source="seodaemun", detail=f"{r['시설구분']} · 관리: {r['관리기관']}")
            for r in read_csv("seodaemun.csv")]


def from_songpa():
    return [Place(name=r["건물명"], address=extract_address(r["도로명주소"], "송파구") or r["도로명주소"], gu="송파구",
                  kind=normalize_kind(r["구분"]), source="songpa") for r in read_csv("songpa.csv")]


def from_yangcheon():
    return [Place(name=r["설치 위치"], address=extract_address(r["설치 위치"], "양천구"), gu="양천구",
                  kind=normalize_kind(r["시설형태"]), source="yangcheon", detail=f"{r['시설 구분']} · 설치: {r['설치기관']}")
            for r in read_csv("yangcheon.csv")]


def from_yeongdeungpo():
    return [Place(name=r["시설 구분"], address=None, gu="영등포구", kind=normalize_kind(r["시설형태"]), source="yeongdeungpo",
                  lat=num(r["위도"]), lng=num(r["경도"]), detail=f"{r['설치 위치']} · 관리: {r['관리']}") for r in read_csv("yeongdeungpo.csv")]


def from_yongsan():
    return [Place(name=r["설치 위치"].replace("서울특별시 용산구 ", ""), address=None, gu="용산구", kind=normalize_kind(r["시설형태"]),
                  source="yongsan", lat=num(r["위도"]), lng=num(r["경도"]), detail=f"{r['시설 구분']} · 설치: {r['설치 주체']}")
            for r in read_csv("yongsan.csv")]


# 출처 표기(공공누리 1유형: 출처표시)와 화면의 "출처" 목록
SOURCES = {
    "seoul": ("서울특별시 실외흡연 시설 현황", "https://data.seoul.go.kr/dataList/OA-22191/F/1/datasetView.do", from_seoul),
    "gwanak": ("서울특별시 관악구 흡연시설현황", "https://www.data.go.kr/data/15040591/fileData.do", from_gwanak),
    "jongno": ("서울특별시 종로구 흡연부스현황", "https://www.data.go.kr/data/15142571/fileData.do", from_jongno),
    "junggu": ("서울특별시 중구 흡연구역정보", "https://www.data.go.kr/data/15080296/fileData.do", from_junggu),
    "jungnang": ("서울특별시 중랑구 흡연시설", "https://www.data.go.kr/data/15040636/fileData.do", from_jungnang),
    "seocho": ("서울특별시 서초구 흡연시설 현황", "https://www.data.go.kr/data/15074379/fileData.do", from_seocho),
    "seodaemun": ("서울특별시 서대문구 흡연시설 현황", "https://www.data.go.kr/data/15040413/fileData.do", from_seodaemun),
    "songpa": ("서울특별시 송파구 실외흡연구역 위치", "https://www.data.go.kr/data/15090343/fileData.do", from_songpa),
    "yangcheon": ("서울특별시 양천구 흡연시설 현황", "https://www.data.go.kr/data/15040511/fileData.do", from_yangcheon),
    "yeongdeungpo": ("서울특별시 영등포구 흡연구역(실외) 현황", "https://www.data.go.kr/data/15069051/fileData.do", from_yeongdeungpo),
    "yongsan": ("서울특별시 용산구 흡연구역", "https://www.data.go.kr/data/15073796/fileData.do", from_yongsan),
}


# ---- 좌표 ----
def nominatim(query: str) -> dict | None:
    """OpenStreetMap 주소 검색(키 없음). 1초에 한 번만 — 사용 정책. 카카오 키가 생기면 kakao()로 바꾼다."""
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": query, "format": "json", "limit": 1, "countrycodes": "kr", "addressdetails": 0})
    req = urllib.request.Request(url, headers={"User-Agent": "smoking-map/0.1 (personal project)"})
    time.sleep(1.1)
    try:
        hits = json.loads(urllib.request.urlopen(req, timeout=30).read())
    except Exception:
        return None
    if not hits:
        return None
    h = hits[0]
    # 동·지역 수준으로만 잡힌 결과는 "대략적 위치"로 표시한다
    approx = h.get("addresstype") in {"suburb", "quarter", "neighbourhood", "city_district", "borough", "city", "road"}
    return {"lat": round(float(h["lat"]), 6), "lng": round(float(h["lon"]), 6), "approx": approx}


def queries_for(p: Place) -> list[str]:
    qs = []
    if p.address:
        qs.append(p.address)
    if p.name:
        qs.append(f"서울특별시 {p.gu} {re.sub(r'[(),]', ' ', p.name)}")
    return qs


def geocode_all(places: list[Place], geocoder, cache: dict) -> tuple[list[Place], list[Place]]:
    placed, unplaced = [], []
    for p in places:
        if p.lat is not None and p.lng is not None:
            placed.append(p)
            continue
        hit = None
        for q in queries_for(p):
            if q not in cache:
                cache[q] = geocoder(q)
            hit = cache[q]
            if hit:
                break
        if hit:
            p.lat, p.lng, p.approx = hit["lat"], hit["lng"], bool(hit.get("approx"))
            placed.append(p)
        else:
            unplaced.append(p)
    return placed, unplaced


def apply_manual(places: list[Place]) -> None:
    """data/manual-coords.csv: name,lat,lng — 자동으로 못 찾은 곳을 사람이 채운다."""
    if not MANUAL.exists():
        return
    fixes = {clean(r["name"]): (float(r["lat"]), float(r["lng"])) for r in csv.DictReader(MANUAL.open(encoding="utf-8-sig"))
             if r.get("lat") and r.get("lng")}
    for p in places:
        if p.lat is None and clean(p.name) in fixes:
            p.lat, p.lng = fixes[clean(p.name)]
            p.approx = False


# ---- 중복 합치기 ----
def meters(a: Place, b: Place) -> float:
    dlat = math.radians(b.lat - a.lat)
    dlng = math.radians(b.lng - a.lng)
    h = math.sin(dlat / 2) ** 2 + math.cos(math.radians(a.lat)) * math.cos(math.radians(b.lat)) * math.sin(dlng / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(h))


def merge_places(places: list[Place]) -> list[Place]:
    """통합 자료(seoul)와 구 자료가 같은 곳을 가리키면 하나로 — 구 자료가 더 자세하니 그쪽을 남긴다.
    같은 건물에 형태가 다른 부스가 둘이면(송파) 둘 다 둔다."""
    ordered = sorted(places, key=lambda p: p.source == "seoul")  # 구 자료 먼저
    kept: list[Place] = []
    for p in ordered:
        twin = next((k for k in kept if meters(k, p) < MERGE_METERS
                     and ("seoul" in (k.source, p.source) or k.kind == p.kind) and k.source != p.source), None)
        if twin:
            twin.sources = sorted(set(twin.sources) | set(p.sources))
            if twin.approx and not p.approx:
                twin.lat, twin.lng, twin.approx = p.lat, p.lng, False
        else:
            kept.append(p)
    return kept


# ---- 실행 ----
def main() -> int:
    manifest = json.loads((RAW / "manifest.json").read_text(encoding="utf-8"))
    places: list[Place] = []
    counts = {}
    for key, (_, _, reader) in SOURCES.items():
        rows = reader()
        counts[key] = len(rows)
        places += rows
    print("읽음:", counts, "합계", len(places))

    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    apply_manual(places)
    try:
        placed, unplaced = geocode_all(places, nominatim, cache)
    finally:
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    merged = merge_places(placed)
    print(f"좌표 {len(placed)} · 못 찾음 {len(unplaced)} · 합친 뒤 {len(merged)}")

    with UNPLACED.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "lat", "lng", "gu", "address", "source"])
        for p in unplaced:
            w.writerow([p.name, "", "", p.gu, p.address or "", p.source])

    merged.sort(key=lambda p: (p.gu, p.name))
    data = {
        "generatedAt": datetime.now().isoformat(timespec="minutes"),
        "sources": [{"key": k, "title": SOURCES[k][0], "url": SOURCES[k][1],
                     "fileTitle": (manifest.get(k) or {}).get("title"), "count": counts[k]} for k in SOURCES],
        "places": [{"id": f"p{i}", **{k: v for k, v in asdict(p).items() if k != "source"}} for i, p in enumerate(merged)],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("저장:", OUT.relative_to(ROOT), f"{OUT.stat().st_size // 1024}KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
