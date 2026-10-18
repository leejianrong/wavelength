<script lang="ts">
  // What the human guesser says while thinking aloud, as the server took it: finished lines in order and the
  // line still being spoken. Shown only for the round being guessed.
  import { app } from "./store.svelte.ts";
  import type { StateMessage } from "./types.ts";

  let { state }: { state: StateMessage } = $props();
  const heard = $derived(app.spoken.round === state.observation.round ? app.spoken : null);
</script>

{#if heard && (heard.lines.length > 0 || heard.partial)}
  <section class="card heard" aria-label="What you said">
    <strong>You are thinking:</strong>
    <ol>
      {#each heard.lines as line, i (i)}<li><em>{line}</em></li>{/each}
      {#if heard.partial}<li class="partial"><em>{heard.partial}</em></li>{/if}
    </ol>
  </section>
{/if}

<style>
  .heard { color: var(--md-sys-color-on-surface-variant); overflow-wrap: anywhere; }
  ol { margin: 6px 0 0; padding-left: 1.4em; display: grid; gap: 4px; }
  li.partial { opacity: 0.7; }
</style>
