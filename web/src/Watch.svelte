<script lang="ts">
  // Two AIs playing and a person watching. The default view is the guesser's (no target); a peek adds it.
  import { setPeek } from "./api.ts";
  import AgentWait from "./AgentWait.svelte";
  import Dial from "./Dial.svelte";
  import { staged, watchedNeedle } from "./store.svelte.ts";
  import type { Spectrum, StateMessage } from "./types.ts";

  let { state }: { state: StateMessage } = $props();
  const obs = $derived(state.observation);
  const spectrum = $derived(obs.spectrum as Spectrum);
  const name = (seat: string) => state.names[seat] ?? seat;
  const other = $derived(state.players.find((p) => p !== obs.you) ?? obs.you);
  const guesser = $derived(obs.role === "guesser" ? obs.you : other);
  const psychic = $derived(obs.role === "psychic" ? obs.you : other);
</script>

<section class="card raised round" aria-label="Round {obs.round}">
  <h2>Round {obs.round} of {obs.rounds}</h2>
  <p>{name(psychic)} is the psychic, {name(guesser)} is the guesser.</p>
  {#if !staged(state)}
    <Dial {spectrum} bands={obs.target === undefined ? undefined : state.scoring} target={obs.target} guess={watchedNeedle(state)} smooth />
  {/if}
  {#if obs.target !== undefined}
    <p class="hint">Peeking: the target is {obs.target} out of 100.</p>
  {/if}
  {#if obs.phase === "clue"}
    <p class="waiting">{name(psychic)} is thinking of a clue…</p>
    <AgentWait {state} seat={psychic} />
  {:else}
    <p class="waiting">The clue: <q>{obs.clue ?? ""}</q> — {name(guesser)} is guessing…</p>
    <AgentWait {state} seat={guesser} />
  {/if}
  <p class="hint">Peeking shows the target and spoils the guess.</p>
  <div>
    <button type="button" id="peek" class="btn btn-tonal" aria-pressed={state.viewer.peek} onclick={() => void setPeek(!state.viewer.peek)}>
      {state.viewer.peek ? "Stop peeking" : "Peek at the target"}
    </button>
  </div>
</section>
