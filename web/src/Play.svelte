<script lang="ts">
  // A human playing: they are the psychic (and see the target) or the guesser.
  import ClueForm from "./ClueForm.svelte";
  import Dial from "./Dial.svelte";
  import GuessForm from "./GuessForm.svelte";
  import { staged, watchedNeedle } from "./store.svelte.ts";
  import type { Spectrum, StateMessage } from "./types.ts";

  let { state }: { state: StateMessage } = $props();
  const obs = $derived(state.observation);
  const onStage = $derived(staged(state));
  const spectrum = $derived(obs.spectrum as Spectrum);
  const other = $derived.by(() => {
    const partner = state.players.find((p) => p !== obs.you) ?? "";
    return state.names[partner] ?? partner;
  });
</script>

<section class="card raised round" aria-label="Round {obs.round}">
  <h2>Round {obs.round} of {obs.rounds}</h2>
  {#if obs.role === "psychic"}
    <p>You are the psychic. Your target: {obs.target} out of 100.</p>
    {#if !onStage}<Dial {spectrum} bands={state.scoring} target={obs.target} guess={watchedNeedle(state)} smooth />{/if}
    {#if state.awaiting === "clue"}
      <ClueForm {state} />
    {:else}
      <p class="waiting">Your clue: "{obs.clue}". {other} is guessing…</p>
    {/if}
  {:else if state.awaiting === "guess"}
    <p class="clue">The clue: <q>{obs.clue ?? ""}</q></p>
    <GuessForm {state} {onStage} />
  {:else}
    <p>You are the guesser.</p>
    {#if !onStage}<Dial {spectrum} />{/if}
    <p class="waiting">{other} is thinking of a clue…</p>
  {/if}
</section>

<style>
  .clue { font: 400 var(--md-sys-typescale-headline-small-size) / var(--md-sys-typescale-headline-small-line-height) var(--md-ref-typeface-brand); }
  .clue q { font-weight: 700; }
</style>
