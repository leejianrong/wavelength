<script lang="ts">
  // The dial that belongs to the current turn, chosen from the state alone. Used by the avatar stage,
  // where the dial sits in the clear band between the two avatars. (Without voice, Play, Watch and
  // GuessForm draw the same dial inside their own cards.)
  import Dial from "./Dial.svelte";
  import { draft, setGuess, watchedNeedle } from "./store.svelte.ts";
  import type { Spectrum, StateMessage } from "./types.ts";

  let { state }: { state: StateMessage } = $props();
  const obs = $derived(state.observation);
  const spectrum = $derived(obs.spectrum as Spectrum);
  const needle = $derived(watchedNeedle(state));
  const guessing = $derived(state.viewer.mode === "player" && obs.role === "guesser" && state.awaiting === "guess");
</script>

{#if guessing}
  <Dial {spectrum} guess={draft.guess} onGuess={setGuess} />
{:else if obs.target !== undefined}
  <Dial {spectrum} bands={state.scoring} target={obs.target} guess={needle} smooth />
{:else}
  <Dial {spectrum} guess={needle} smooth />
{/if}
