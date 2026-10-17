<script lang="ts">
  // The dial that belongs to the current turn, chosen from the state alone. Used by the avatar stage,
  // where the dial sits in the clear band between the two avatars. (Without voice, Play, Watch and
  // GuessForm draw the same dial inside their own cards.)
  import { clampValue } from "./dial.ts";
  import Dial from "./Dial.svelte";
  import { draft } from "./store.svelte.ts";
  import type { Spectrum, StateMessage } from "./types.ts";

  let { state }: { state: StateMessage } = $props();
  const obs = $derived(state.observation);
  const spectrum = $derived(obs.spectrum as Spectrum);
  const guessing = $derived(state.viewer.mode === "player" && obs.role === "guesser" && state.awaiting === "guess");
</script>

{#if guessing}
  <Dial {spectrum} guess={draft.guess} onGuess={(value) => (draft.guess = clampValue(value))} />
{:else if obs.target !== undefined}
  <Dial {spectrum} bands={state.scoring} target={obs.target} />
{:else}
  <Dial {spectrum} />
{/if}
