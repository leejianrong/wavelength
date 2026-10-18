<script lang="ts">
  // A finished round on a dial: the needle sweeps from the middle to the guess, then the scoring bands
  // and the target appear (and, with `showPoints`, the points land on the dial). Not staged, or with
  // motion reduced, it is shown at rest. Used by the result card and by the avatar stage.
  import { untrack } from "svelte";
  import { cubicOut } from "svelte/easing";
  import { Tween } from "svelte/motion";
  import { prefersReducedMotion } from "./a11y.ts";
  import Dial from "./Dial.svelte";
  import type { Reveal, StateMessage } from "./types.ts";

  let {
    reveal,
    view,
    staged,
    showPoints = false,
    onSettled,
  }: {
    reveal: Reveal;
    view: StateMessage;
    staged: boolean;
    showPoints?: boolean;
    onSettled?: () => void;
  } = $props();

  // Decided once, when this dial appears.
  const animate = untrack(() => staged && !prefersReducedMotion());
  const needle = new Tween(untrack(() => (animate ? 50 : reveal.guess)), { duration: 750, easing: cubicOut });
  let settled = $state(!animate);
  if (animate) {
    void needle.set(untrack(() => reveal.guess)).then(() => {
      settled = true;
      onSettled?.();
    });
  }
</script>

<Dial
  spectrum={reveal.spectrum}
  bands={settled ? view.scoring : undefined}
  target={settled ? reveal.target : undefined}
  guess={needle.current}
  label={showPoints && settled ? `+${reveal.points}` : undefined}
/>
