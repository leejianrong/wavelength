import assert from "node:assert/strict";
import { test } from "node:test";
import { arcPath, bandArcs, clampText, clampValue, countWords, pointToValue, polar, valueToAngle } from "../src/dial.ts";
import { readResults } from "../src/speech.ts";

const near = (a: number, b: number) => assert.ok(Math.abs(a - b) < 1e-9, `${a} !~ ${b}`);

test("the ends and the middle of the dial are the ends and the middle of the half circle", () => {
  near(valueToAngle(0), Math.PI);
  near(valueToAngle(50), Math.PI / 2);
  near(valueToAngle(100), 0);
});

test("polar puts 0 on the left, 100 on the right and 50 straight up", () => {
  const left = polar(100, 100, 80, 0);
  const right = polar(100, 100, 80, 100);
  const top = polar(100, 100, 80, 50);
  near(left.x, 20);
  near(left.y, 100);
  near(right.x, 180);
  near(top.x, 100);
  near(top.y, 20);
});

test("a pointer maps back to the value it was drawn at", () => {
  for (const v of [0, 1, 17, 50, 64, 99, 100]) {
    const p = polar(100, 100, 80, v);
    assert.equal(pointToValue(p.x, p.y, 100, 100), v);
  }
});

test("a pointer below the centre line snaps to the nearer end", () => {
  assert.equal(pointToValue(10, 150, 100, 100), 0);
  assert.equal(pointToValue(190, 150, 100, 100), 100);
});

test("values are clamped and rounded to the dial", () => {
  assert.equal(clampValue(-5), 0);
  assert.equal(clampValue(140), 100);
  assert.equal(clampValue(41.6), 42);
});

test("scoring zones are widest first, centred on the target and cut off at the ends", () => {
  const arcs = bandArcs(97, [
    { within: 2, points: 4 },
    { within: 10, points: 2 },
    { within: 6, points: 3 },
  ]);
  assert.deepEqual(arcs, [
    { points: 2, from: 87, to: 100 },
    { points: 3, from: 91, to: 100 },
    { points: 4, from: 95, to: 99 },
  ]);
});

test("an arc path is a closed ring segment", () => {
  const d = arcPath(100, 100, 60, 80, 0, 100);
  assert.match(d, /^M .* A 80 80 0 0 1 .* L .* A 60 60 0 0 0 .* Z$/);
});

test("words are counted the way the clue rule counts them", () => {
  assert.equal(countWords(""), 0);
  assert.equal(countWords("   "), 0);
  assert.equal(countWords("a lazy afternoon"), 3);
  assert.equal(countWords("  two   spaces "), 2);
});

test("a spoken clue is cut at a word to fit the clue box", () => {
  assert.equal(clampText("  ocean waves at night  ", 80), "ocean waves at night");
  assert.equal(clampText("ocean waves at night", 12), "ocean waves");
  assert.equal(clampText("oceanwaves", 5), "ocean");
});

test("a recogniser event is read as finished lines and one partial", () => {
  const result = (text: string, isFinal: boolean) => Object.assign([{ transcript: text }], { isFinal }) as never;
  const out = readResults({
    resultIndex: 0,
    results: [result(" it sounds calm ", true), result("maybe", false), result("sixty", false)],
  });
  assert.deepEqual(out, [
    { text: "it sounds calm", final: true },
    { text: "maybe sixty", final: false },
  ]);
});
