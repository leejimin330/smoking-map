# 서울 흡연구역 지도

내 위치에서 가장 가까운 서울 공공 흡연구역을 찾고 카카오맵으로 길을 안내한다.

## 자료 만들기

```bash
python -m venv .venv && .venv/Scripts/pip install openpyxl pytest
.venv/Scripts/python scripts/build.py      # data/raw/* → web/data/places.json
```

- 원자료: 서울시 실외흡연 시설 현황(통합) + 구별 흡연시설 파일(`data/raw`, 출처는 `scripts/build.py`의 SOURCES).
- 주소 → 좌표: 지금은 OpenStreetMap 검색(키 없음, 1초에 1건). 결과는 `data/geocode-cache.json`에 남는다.
- 못 찾은 곳은 `data/unplaced.csv`. `data/manual-coords.csv`(name,lat,lng)에 좌표를 적으면 다음 빌드에 들어간다.

## 실행

`흡연지도-서버-켜기.bat` 또는 `python -m http.server 8752 --directory web` → http://localhost:8752

휴대폰에서 "내 주변"(위치)을 쓰려면 HTTPS 주소에 올려야 한다(GitHub Pages 등).

## 테스트

```bash
.venv/Scripts/python -m pytest -q   # 자료 합치기·주소 뽑기·좌표 캐시
node --test tests/geo.test.mjs       # 거리·가까운 순·길찾기 링크
```

## 지도 바꾸기

지도는 `web/map-leaflet.js` 한 파일에 있다. 카카오맵으로 바꿀 때는 같은 메서드(`setPlaces`, `select`, `showMe`, `fit`, `resize`)를 가진 `map-kakao.js`를 만들고 `app.js`의 import만 바꾼다.
