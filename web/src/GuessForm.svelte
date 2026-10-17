<script lang="ts">
  import { postMove } from "./api.ts";
  import { focusOnTurn } from "./a11y.ts";
  import { clampValue } from "./dial.ts";
  import Dial from "./Dial.svelte";
  import { app, draft } from "./store.svelte.ts";
  import type { Spectrum, StateMessage } from "./types.ts";

  let { state }: { state: StateMessage } = $props();
  const spectrum = $derived(state.observation.spectrum as Spectrum);

  async function submit(e: SubmitEvent) {
    e.preventDefault();
    if (draft.submitting) return;
    draft.submitting = true;
    const problem = await postMove({ type: "guess", value: draft.guess });
    if (problem) {
      draft.submitting = false;
      app.notice = problem;
    }
  }
</script>

<form class="guess" onsubmit={submit}>
  <Dial {spectrum} guess={draft.guess} onGuess={(value) => (draft.guess = clampValue(value))} />
  <input
    id="guess"
    type="range"
    min="0"
    max="100"
    step="1"
    bind:value={draft.guess}
    {@attach focusOnTurn}
    aria-label="Your guess from 0 ({spectrum.left}) to 100 ({spectrum.right})"
  />
  <div class="row">
    <output id="guess-value" for="guess">{draft.guess}</output>
    <button type="submit" class="btn btn-filled" disabled={draft.submitting}>Lock in {draft.guess}</button>
  </div>
</form>

<style>
  .guess { display: grid; gap: 12px; }
  .row { justify-content: space-between; }
  output { font: 600 var(--md-sys-typescale-headline-medium-size) / 1 var(--md-ref-typeface-brand); min-width: 3ch; font-variant-numeric: tabular-nums; }
</style>
