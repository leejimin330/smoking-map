from build import Place, extract_address, geocode_all, merge_places, normalize_kind


def place(**kw):
    base = dict(name="흡연부스", address="서울특별시 중구 을지로 35", gu="중구", kind="partial",
                source="junggu", lat=37.5664, lng=126.9819)
    base.update(kw)
    return Place(**base)


def test_normalize_kind_reads_the_many_spellings():
    assert normalize_kind("폐쇄형") == "closed"
    assert normalize_kind("완전폐쇄형") == "closed"
    assert normalize_kind("부분폐쇄형") == "partial"
    assert normalize_kind("부분 개방형") == "partial"
    assert normalize_kind("부분 개방형(부스)") == "partial"
    assert normalize_kind("완전 개방형") == "open"
    assert normalize_kind("개방형흡연구역") == "open"
    assert normalize_kind("개방형") == "open"
    assert normalize_kind("") == "partial"  # 모르면 가장 흔한 형태로


def test_extract_address_finds_a_road_address_inside_a_description():
    assert extract_address("교보타워(강남대로 465) 부지주차장 진입로 옆", "서초구") == "서울특별시 서초구 강남대로 465"
    assert extract_address("강남대로 213 엘타워 뒤 주차장 진입로 옆", "서초구") == "서울특별시 서초구 강남대로 213"
    assert extract_address("서울특별시 송파구 법원로 11길 11 현대지식산업센터 A동", "송파구") == "서울특별시 송파구 법원로11길 11"
    assert extract_address(" 중구 남대문로5가 520", "중구") == "서울특별시 중구 남대문로5가 520"
    assert extract_address("낙원악기상가(낙원동 260-1 도로일부)", "종로구") == "서울특별시 종로구 낙원동 260-1"
    assert extract_address("양천구청 부지", "양천구") is None


def test_merge_joins_the_city_list_with_the_district_list():
    city = place(name="센터플레이스 측면부", source="seoul", lat=37.56640, lng=126.98190)
    district = place(name="하나은행본점 측면부", source="junggu", lat=37.56645, lng=126.98185)
    merged = merge_places([city, district])
    assert len(merged) == 1
    assert merged[0].name == "하나은행본점 측면부"  # 구 자료가 더 자세하다
    assert merged[0].sources == ["junggu", "seoul"]


def test_merge_keeps_two_booths_of_different_kinds_at_one_building():
    a = place(source="songpa", kind="partial")
    b = place(source="songpa", kind="open")
    assert len(merge_places([a, b])) == 2


def test_merge_keeps_places_far_apart():
    a = place(source="seoul")
    b = place(source="junggu", lat=37.5700)
    assert len(merge_places([a, b])) == 2


def test_geocode_uses_the_cache_and_reports_what_it_could_not_place():
    calls = []

    def fake(query):
        calls.append(query)
        return {"lat": 37.5, "lng": 127.0, "approx": False} if "을지로" in query else None

    cache = {}
    places = [place(lat=None, lng=None), place(lat=None, lng=None, name="모르는 곳", address=None)]
    placed, unplaced = geocode_all(places, fake, cache)
    assert [p.lat for p in placed] == [37.5]
    assert [p.name for p in unplaced] == ["모르는 곳"]
    first_calls = len(calls)
    geocode_all([place(lat=None, lng=None)], fake, cache)
    assert len(calls) == first_calls  # 캐시에서 꺼낸다


def test_clean_address_drops_lot_word_and_floor():
    from build import clean_address
    assert clean_address("서울특별시 중랑구 면목동 359-15번지 지하1층") == "서울특별시 중랑구 면목동 359-15"
    assert clean_address("서울특별시 중랑구 면목동 103-5번지 지상2,3층") == "서울특별시 중랑구 면목동 103-5"
    assert clean_address("서울특별시 중랑구 봉화산로 179(신내동)") == "서울특별시 중랑구 봉화산로 179"
    assert clean_address("서울특별시 중랑구 상봉동 88-95번지") == "서울특별시 중랑구 상봉동 88-95"
