// The six zones of a spectrum (ADR-0007). The same rule as `deck.region_index` in Python; both are
// checked against tests/data/region_index.json, so they cannot drift apart.

export const REGION_COUNT = 6;

/** Which zone a dial value is in: 0 is the left extreme, 5 the right. */
export function regionIndex(value: number): number {
  const v = Math.min(100, Math.max(0, Math.round(value)));
  return Math.min(REGION_COUNT - 1, Math.floor((v * REGION_COUNT) / 100));
}

/** The first dial value of zone `index` (the zone before the next one starts). */
export function regionStart(index: number): number {
  return Math.ceil((index * 100) / REGION_COUNT);
}

/** The written name of the zone a value is in. */
export function regionName(regions: string[], value: number): string {
  return regions[regionIndex(value)] ?? "";
}
