<script lang="ts">
  // What a screen-reader user needs to be told when the screen changes: a finished round, and whose turn it is.
  // Built only from what this seat may already see (the revealed rounds and the turn), never the hidden target.
  import { app } from "./store.svelte.ts";

  const message = $derived.by(() => {
    const state = app.state;
    if (!state) return "";
    const obs = state.observation;
    const last = obs.history[obs.history.length - 1];
    const result = last
      ? `Round ${last.round} result: ${last.points} point${last.points === 1 ? "" : "s"}. Target ${last.target}, guess ${last.guess}. `
      : "";
    if (obs.phase === null) return `${result}The match has ended with ${obs.total_score} of ${obs.target_score} points.`;
    if (state.awaiting === "clue") return `${result}Round ${obs.round}: your turn, give a clue.`;
    if (state.awaiting === "guess") return `${result}Round ${obs.round}: your turn, guess from 0 to 100. The clue is ${obs.clue}.`;
    return result;
  });
</script>

<div class="sr-only" role="status" aria-live="polite">{message}</div>
