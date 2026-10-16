import { arcPath, bandArcs, pointToValue, polar } from "./dial.ts";
import { svg } from "./draw.ts";
import { REGION_COUNT, regionIndex, regionStart } from "./regions.ts";
import type { Band, Spectrum } from "./types.ts";

const CX = 200;
const CY = 190;
const R_OUT = 170;
const R_IN = 105;

export interface DialOptions {
  spectrum: Spectrum;
  bands?: Band[];
  target?: number;
  guess?: number;
  onGuess?: (value: number) => void;
}

/** The half-circle dial. With `target` it draws the scoring zones and a marker; with `guess` a needle;
 *  with `onGuess` the needle can be dragged. */
export function dial(opts: DialOptions): { svg: SVGSVGElement; setGuess(value: number): void } {
  const root = svg("svg", {
    viewBox: "0 0 400 235",
    class: opts.onGuess ? "dial interactive" : "dial",
    role: "img",
    "aria-label": `Dial from ${opts.spectrum.left} to ${opts.spectrum.right}`,
  });
  // The six zones, with the active one lit: the zone of the guess while guessing, else of the target.
  const zones = Array.from({ length: REGION_COUNT }, (_, i) =>
    svg(
      "path",
      {
        d: arcPath(CX, CY, R_IN, R_OUT, regionStart(i), i === REGION_COUNT - 1 ? 100 : regionStart(i + 1)),
        class: `zone zone-${i % 2}`,
      },
      root,
    ),
  );
  const light = (value: number | undefined) =>
    zones.forEach((z, i) => z.classList.toggle("zone-active", value !== undefined && i === regionIndex(value)));
  light(opts.onGuess ? opts.guess : opts.target);
  if (opts.target !== undefined && opts.bands) {
    for (const arc of bandArcs(opts.target, opts.bands)) {
      svg("path", { d: arcPath(CX, CY, R_IN, R_OUT, arc.from, arc.to), class: `band band-${arc.points}` }, root);
    }
  }
  if (opts.target !== undefined) {
    const a = polar(CX, CY, R_IN - 8, opts.target);
    const b = polar(CX, CY, R_OUT + 10, opts.target);
    svg("line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y, class: "target" }, root);
  }
  svg("text", { x: CX - R_OUT, y: CY + 32, class: "end start" }, root).textContent = opts.spectrum.left;
  svg("text", { x: CX + R_OUT, y: CY + 32, class: "end finish" }, root).textContent = opts.spectrum.right;

  const needle = svg("g", { class: "needle" }, root);
  const line = svg("line", { x1: CX, y1: CY, x2: CX, y2: CY, class: "needle-line" }, needle);
  const knob = svg("circle", { cx: CX, cy: CY, r: 9, class: "knob" }, needle);
  if (opts.guess !== undefined) svg("circle", { cx: CX, cy: CY, r: 7, class: "hub" }, root);
  const setGuess = (value: number) => {
    const tip = polar(CX, CY, R_OUT - 6, value);
    line.setAttribute("x2", String(tip.x));
    line.setAttribute("y2", String(tip.y));
    knob.setAttribute("cx", String(tip.x));
    knob.setAttribute("cy", String(tip.y));
    needle.setAttribute("visibility", "visible");
    if (opts.onGuess) light(value);
  };
  if (opts.guess === undefined) needle.setAttribute("visibility", "hidden");
  else setGuess(opts.guess);

  if (opts.onGuess) {
    const onGuess = opts.onGuess;
    root.style.touchAction = "none";
    let dragging = false;
    const move = (e: PointerEvent) => {
      const ctm = root.getScreenCTM();
      if (!ctm) return;
      const pt = root.createSVGPoint();
      pt.x = e.clientX;
      pt.y = e.clientY;
      const local = pt.matrixTransform(ctm.inverse());
      onGuess(pointToValue(local.x, local.y, CX, CY));
    };
    root.addEventListener("pointerdown", (e) => {
      dragging = true;
      root.setPointerCapture(e.pointerId);
      move(e);
    });
    root.addEventListener("pointermove", (e) => dragging && move(e));
    root.addEventListener("pointerup", () => (dragging = false));
    root.addEventListener("pointercancel", () => (dragging = false));
  }
  return { svg: root, setGuess };
}
