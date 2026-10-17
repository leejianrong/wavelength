<script lang="ts">
  // The result of a round. A reveal that arrives while you watch is staged: the needle sweeps from the
  // middle to the guess, then the scoring bands and the target appear, then the points land. One that was
  // already there when the page loaded (a reload) is shown at rest, and so is any reveal when motion is reduced.
  import { untrack } from "svelte";
  import { cubicOut } from "svelte/easing";
  import { Tween } from "svelte/motion";
  import { prefersReducedMotion } from "./a11y.ts";
  import Dial from "./Dial.svelte";
  import { seen } from "./store.svelte.ts";
  import type { Reveal, StateMessage } from "./types.ts";

  let { reveal, state: view }: { reveal: Reveal; state: StateMessage } = $props();
  const who = $derived(view.names[reveal.psychic] ?? reveal.psychic);

  // Decided once, when this card appears (App keys it by round).
  const staged = untrack(() => reveal.round > seen.round && !prefersReducedMotion());
  const needle = new Tween(untrack(() => (staged ? 50 : reveal.guess)), { duration: 750, easing: cubicOut });
  let settled = $state(!staged);
  if (staged) void needle.set(untrack(() => reveal.guess)).then(() => (settled = true));
</script>

<section class="card reveal" aria-label="Round {reveal.round} result">
  <h2>Round {reveal.round} result</h2>
  <div class="small">
    <Dial
      spectrum={reveal.spectrum}
      bands={settled ? view.scoring : undefined}
      target={settled ? reveal.target : undefined}
      guess={needle.current}
    />
  </div>
  {#if settled}
    <p class="points" class:staged class:full={reveal.points === Math.max(...view.scoring.map((b) => b.points))} aria-hidden="true">
      +{reveal.points}
    </p>
  {/if}
  <p>
    <strong>{reveal.points} point{reveal.points === 1 ? "" : "s"}</strong>
    · {who} said "{reveal.clue}" · target {reveal.target} out of 100, guess {reveal.guess}
  </p>
</section>

<style>
  .small { max-width: 300px; width: 100%; margin-inline: auto; }
  .points {
    text-align: center;
    font: 700 var(--md-sys-typescale-display-medium-size) / 1 var(--md-ref-typeface-brand);
    color: var(--md-sys-color-on-surface-variant);
    font-variant-numeric: tabular-nums;
  }
  .points.full { color: var(--md-sys-color-primary); }
  .points.staged { animation: land var(--md-sys-motion-duration-medium4) var(--md-sys-motion-easing-emphasized-decelerate) both; }
  @keyframes land { from { opacity: 0; transform: translateY(12px) scale(0.8); } to { opacity: 1; transform: none; } }
</style>
