import assert from "node:assert/strict";
import { test } from "node:test";
import { directionsUrl, distanceMeters, formatDistance, nearest, walkMinutes } from "../web/geo.js";

const cityHall = { lat: 37.5663, lng: 126.9779 };
const place = (id, lat, lng, kind = "partial") => ({ id, name: id, lat, lng, kind });

test("distance between Seoul City Hall and Seoul Station is about 1.4km", () => {
  const d = distanceMeters(cityHall, { lat: 37.5547, lng: 126.9707 });
  assert.ok(d > 1300 && d < 1500, String(d));
});

test("nearest returns the closest places first, only of the kinds asked for", () => {
  const places = [place("far", 37.60, 126.98), place("near", 37.567, 126.978), place("mid", 37.57, 126.98), place("indoor", 37.5664, 126.9779, "indoor")];
  const got = nearest(places, cityHall, 2, new Set(["partial"]));
  assert.deepEqual(got.map((x) => x.place.id), ["near", "mid"]);
  assert.ok(got[0].meters < got[1].meters);
});

test("walking time and distance labels", () => {
  assert.equal(walkMinutes(30), 1);
  assert.equal(walkMinutes(670), 10);
  assert.equal(formatDistance(350.4), "350m");
  assert.equal(formatDistance(1234), "1.2km");
});

test("directions link opens Kakao Map with the place as the destination", () => {
  assert.equal(directionsUrl({ name: "서울역 8번출구", lat: 37.5547, lng: 126.9707 }),
    "https://map.kakao.com/link/to/%EC%84%9C%EC%9A%B8%EC%97%AD%208%EB%B2%88%EC%B6%9C%EA%B5%AC,37.5547,126.9707");
});
