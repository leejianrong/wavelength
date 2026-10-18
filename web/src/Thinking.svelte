<script lang="ts">
  // What the guesser is thinking while it works the needle, as the server sent it: public text only,
  // this round's steps in order, shown only while that round is being guessed.
  import { app } from "./store.svelte.ts";
  import type { StateMessage } from "./types.ts";

  let { state }: { state: StateMessage } = $props();
  const note = $derived(app.thinking);
  const shown = $derived(
    note !== null && state.observation.phase === "guess" && note.round === state.observation.round ? note : null,
  );
</script>

{#if shown}
  <section class="card thinking" aria-label="Thinking">
    <strong>{state.names[shown.seat] ?? shown.seat} is thinking:</strong>
    <ol>
      {#each shown.steps as line, i (i)}
        <li class:latest={i === shown.steps.length - 1}><em>{line}</em></li>
      {/each}
    </ol>
  </section>
{/if}

<style>
  .thinking { color: var(--md-sys-color-on-surface-variant); overflow-wrap: anywhere; }
  ol { margin: 6px 0 0; padding-left: 1.4em; display: grid; gap: 4px; }
  li.latest { color: var(--md-sys-color-on-surface); }
</style>
