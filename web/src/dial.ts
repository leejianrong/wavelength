// The dial's geometry. Value 0 is the left end of the half circle, 100 the right end.
// Pure functions, unit-tested in test/dial.test.ts.

export const DIAL_MIN = 0;
export const DIAL_MAX = 100;

export interface Point {
  x: number;
  y: number;
}

export function clampValue(value: number): number {
  return Math.min(DIAL_MAX, Math.max(DIAL_MIN, Math.round(value)));
}

/** Angle in radians, measured from the positive x axis: 0 -> pi (left), 100 -> 0 (right). */
export function valueToAngle(value: number): number {
  return Math.PI * (1 - clampValue(value) / DIAL_MAX);
}

export function polar(cx: number, cy: number, radius: number, value: number): Point {
  const angle = valueToAngle(value);
  return { x: cx + radius * Math.cos(angle), y: cy - radius * Math.sin(angle) };
}

/** The dial value for a pointer at (x, y). A pointer below the centre line snaps to the nearer end. */
export function pointToValue(x: number, y: number, cx: number, cy: number): number {
  const dx = x - cx;
  const dy = cy - y;
  if (dy < 0) return dx < 0 ? DIAL_MIN : DIAL_MAX;
  const angle = Math.atan2(dy, dx);
  return clampValue(DIAL_MAX * (1 - angle / Math.PI));
}

/** An SVG path for the ring segment between two values. */
export function arcPath(cx: number, cy: number, inner: number, outer: number, from: number, to: number): string {
  const a = polar(cx, cy, outer, from);
  const b = polar(cx, cy, outer, to);
  const c = polar(cx, cy, inner, to);
  const d = polar(cx, cy, inner, from);
  const f = (n: number) => n.toFixed(2);
  return (
    `M ${f(a.x)} ${f(a.y)} A ${outer} ${outer} 0 0 1 ${f(b.x)} ${f(b.y)} ` +
    `L ${f(c.x)} ${f(c.y)} A ${inner} ${inner} 0 0 0 ${f(d.x)} ${f(d.y)} Z`
  );
}

export interface BandArc {
  points: number;
  from: number;
  to: number;
}

/** The scoring zones around a target, widest first so narrower ones are drawn on top. */
export function bandArcs(target: number, bands: { within: number; points: number }[]): BandArc[] {
  return [...bands]
    .sort((p, q) => q.within - p.within)
    .map((b) => ({
      points: b.points,
      from: clampValue(target - b.within),
      to: clampValue(target + b.within),
    }));
}

/** `text` cut to at most `max` characters, at a word where there is one. */
export function clampText(text: string, max: number): string {
  const trimmed = text.trim();
  if (trimmed.length <= max) return trimmed;
  const cut = trimmed.slice(0, max);
  const space = cut.lastIndexOf(" ");
  return (space > 0 ? cut.slice(0, space) : cut).trim();
}

export function countWords(text: string): number {
  const trimmed = text.trim();
  return trimmed === "" ? 0 : trimmed.split(/\s+/).length;
}
