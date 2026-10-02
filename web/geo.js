// 거리·가까운 순·길찾기 — 지도 종류(오픈스트리트맵/카카오)와 상관없는 계산만 둔다.

const R = 6371000;
const rad = (d) => (d * Math.PI) / 180;

/** 두 지점 사이 거리(m), 하버사인 공식. */
export function distanceMeters(a, b) {
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

/** 가까운 순으로 n곳. kinds에 든 시설 형태만. */
export function nearest(places, here, n, kinds) {
  return places
    .filter((p) => !kinds || kinds.has(p.kind))
    .map((place) => ({ place, meters: distanceMeters(here, place) }))
    .sort((a, b) => a.meters - b.meters)
    .slice(0, n);
}

/** 걸어서 몇 분(분속 67m ≈ 시속 4km). */
export function walkMinutes(meters) {
  return Math.max(1, Math.round(meters / 67));
}

export function formatDistance(meters) {
  return meters < 1000 ? `${Math.round(meters)}m` : `${(meters / 1000).toFixed(1)}km`;
}

/** 카카오맵 길찾기 — 키 없이 쓰는 공개 링크. 도착지를 이 흡연구역으로. */
export function directionsUrl(place) {
  return `https://map.kakao.com/link/to/${encodeURIComponent(place.name)},${place.lat},${place.lng}`;
}
