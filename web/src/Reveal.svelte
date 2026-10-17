<script lang="ts">
  import Dial from "./Dial.svelte";
  import type { Reveal, StateMessage } from "./types.ts";

  let { reveal, state }: { reveal: Reveal; state: StateMessage } = $props();
  const who = $derived(state.names[reveal.psychic] ?? reveal.psychic);
</script>

<section class="card reveal" aria-label="Round {reveal.round} result">
  <h2>Round {reveal.round} result</h2>
  <div class="small">
    <Dial spectrum={reveal.spectrum} bands={state.scoring} target={reveal.target} guess={reveal.guess} />
  </div>
  <p>
    <strong>{reveal.points} point{reveal.points === 1 ? "" : "s"}</strong>
    · {who} said "{reveal.clue}" · target {reveal.target} out of 100, guess {reveal.guess}
  </p>
</section>

<style>
  .small { max-width: 300px; width: 100%; margin-inline: auto; }
</style>
