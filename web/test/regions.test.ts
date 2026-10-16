import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { regionIndex, regionName, regionStart } from "../src/regions.ts";

const golden = JSON.parse(readFileSync(new URL("../../tests/data/region_index.json", import.meta.url), "utf8")) as number[];

test("the zone of every dial value matches the table the Python side is tested against", () => {
  assert.equal(golden.length, 101);
  assert.deepEqual(
    Array.from({ length: 101 }, (_, v) => regionIndex(v)),
    golden,
  );
});

test("each zone starts where the table says it does", () => {
  for (let i = 0; i < 6; i++) {
    assert.equal(regionIndex(regionStart(i)), i);
    if (i > 0) assert.equal(regionIndex(regionStart(i) - 1), i - 1);
  }
});

test("values outside the dial are clamped and the name is the written one", () => {
  const regions = ["a", "b", "c", "d", "e", "f"];
  assert.equal(regionName(regions, -3), "a");
  assert.equal(regionName(regions, 50), "d");
  assert.equal(regionName(regions, 100), "f");
  assert.equal(regionName(regions, 400), "f");
  assert.equal(regionName([], 10), "");
});
