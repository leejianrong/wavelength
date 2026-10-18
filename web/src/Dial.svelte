<script lang="ts">
  // The half-circle tuning dial. With `target` it shows the scoring bands and a marker; with `guess` a
  // needle; with `onGuess` the needle can be dragged. Geometry lives in dial.ts (unit-tested).
  import { arcPath, bandArcs, pointToValue, polar } from "./dial.ts";
  import type { Band, Spectrum } from "./types.ts";

  const CX = 200;
  const CY = 190;
  const R_OUT = 170;
  const R_IN = 105;

  let {
    spectrum,
    bands,
    target,
    guess,
    label,
    onGuess,
  }: {
    spectrum: Spectrum;
    bands?: Band[];
    target?: number;
    guess?: number;
    /** Text drawn large above the hub, such as the points of a round. */
    label?: string;
    onGuess?: (value: number) => void;
  } = $props();

  let root: SVGSVGElement | undefined = $state();
  let dragging = false;

  const ticks = Array.from({ length: 21 }, (_, i) => {
    const value = i * 5;
    const major = value % 25 === 0;
    return { a: polar(CX, CY, R_IN - 5, value), b: polar(CX, CY, R_IN - (major ? 19 : 12), value), major };
  });
  const arcs = $derived(target !== undefined && bands ? bandArcs(target, bands) : []);
  const mark = $derived(
    target === undefined ? null : { a: polar(CX, CY, R_IN - 8, target), b: polar(CX, CY, R_OUT + 10, target) },
  );
  const tip = $derived(guess === undefined ? null : polar(CX, CY, R_OUT - 6, guess));

  function move(e: PointerEvent) {
    const ctm = root?.getScreenCTM();
    if (!root || !ctm || !onGuess) return;
    const point = root.createSVGPoint();
    point.x = e.clientX;
    point.y = e.clientY;
    const local = point.matrixTransform(ctm.inverse());
    onGuess(pointToValue(local.x, local.y, CX, CY));
  }
</script>

<svg
  bind:this={root}
  viewBox="0 0 400 235"
  class="dial"
  class:interactive={onGuess !== undefined}
  role="img"
  aria-label="Dial from {spectrum.left} to {spectrum.right}"
  style:touch-action={onGuess ? "none" : undefined}
  onpointerdown={(e) => {
    if (!onGuess) return;
    dragging = true;
    root?.setPointerCapture(e.pointerId);
    move(e);
  }}
  onpointermove={(e) => dragging && move(e)}
  onpointerup={() => (dragging = false)}
  onpointercancel={() => (dragging = false)}
>
  <path d={arcPath(CX, CY, R_IN, R_OUT, 0, 100)} class="track" />
  {#each arcs as arc (arc.points)}
    <path d={arcPath(CX, CY, R_IN, R_OUT, arc.from, arc.to)} class="band band-{arc.points}" />
  {/each}
  {#each ticks as t}
    <line x1={t.a.x} y1={t.a.y} x2={t.b.x} y2={t.b.y} class="tick" class:major={t.major} />
  {/each}
  {#if mark}
    <line x1={mark.a.x} y1={mark.a.y} x2={mark.b.x} y2={mark.b.y} class="target" />
  {/if}
  {#if label}
    <text x={CX} y={CY - 38} class="label">{label}</text>
  {/if}
  <text x={CX - R_OUT} y={CY + 34} class="end start">{spectrum.left}</text>
  <text x={CX + R_OUT} y={CY + 34} class="end finish">{spectrum.right}</text>
  {#if tip}
    <g class="needle">
      <line x1={CX} y1={CY} x2={tip.x} y2={tip.y} class="needle-line" />
      <circle cx={tip.x} cy={tip.y} r="9" class="knob" />
    </g>
    <circle cx={CX} cy={CY} r="7" class="hub" />
  {/if}
</svg>

<style>
  .dial { width: 100%; max-width: 440px; height: auto; display: block; margin-inline: auto; }
  .dial.interactive { cursor: pointer; }
  .track { fill: var(--md-sys-color-surface-container-highest); }
  .band-4 { fill: var(--md-sys-color-primary); }
  .band-3 { fill: var(--md-sys-color-primary-container); }
  .band-2 { fill: var(--md-sys-color-secondary-container); }
  .tick { stroke: var(--md-sys-color-outline); stroke-width: 1.5; stroke-linecap: round; }
  .tick.major { stroke: var(--md-sys-color-on-surface-variant); stroke-width: 2.5; }
  .target { stroke: var(--md-sys-color-on-surface); stroke-width: 3; stroke-dasharray: 4 3; }
  .needle-line { stroke: var(--md-sys-color-primary); stroke-width: 5; stroke-linecap: round; }
  .knob { fill: var(--md-sys-color-primary); stroke: var(--md-sys-color-surface-container-low); stroke-width: 3; }
  .hub { fill: var(--md-sys-color-primary); }
  .end { fill: var(--md-sys-color-on-surface); font: 600 17px var(--md-ref-typeface-brand); }
  .label { fill: var(--md-sys-color-primary); font: 700 64px var(--md-ref-typeface-brand); text-anchor: middle; font-variant-numeric: tabular-nums; animation: land var(--md-sys-motion-duration-medium4) var(--md-sys-motion-easing-emphasized-decelerate) both; }
  @keyframes land { from { opacity: 0; } to { opacity: 1; } }
  .start { text-anchor: start; }
  .finish { text-anchor: end; }
</style>
