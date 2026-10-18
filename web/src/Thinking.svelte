<script lang="ts">
  // What the guesser is thinking while it works the needle, as the server sent it: public text only,
  // shown for the round it belongs to and only while that round is being guessed.
  import { app } from "./store.svelte.ts";
  import type { StateMessage } from "./types.ts";

  let { state }: { state: StateMessage } = $props();
  const note = $derived(app.thinking);
  const shown = $derived(
    note !== null && state.observation.phase === "guess" && note.round === state.observation.round ? note : null,
  );
</script>

{#if shown}
  <p class="card thinking" aria-label="Thinking">
    <strong>{state.names[shown.seat] ?? shown.seat} is thinking:</strong> <em>{shown.text}</em>
  </p>
{/if}

<style>
  .thinking { margin: 0; color: var(--md-sys-color-on-surface-variant); overflow-wrap: anywhere; }
</style>
