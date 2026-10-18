<script lang="ts">
  // After a reveal an AI psychic reacts. The target is public by then, so its notes may be read, but
  // only when asked for: they are folded away.
  import { app } from "./store.svelte.ts";
  import type { StateMessage } from "./types.ts";

  let { state, round }: { state: StateMessage; round: number } = $props();
  const reaction = $derived(app.reaction !== null && app.reaction.round === round ? app.reaction : null);
  const who = $derived(reaction ? (state.names[reaction.seat] ?? reaction.seat) : "");
</script>

{#if reaction}
  <section class="card reaction" aria-label="{who} reacts">
    {#if reaction.text}<p><strong>{who}:</strong> <em>{reaction.text}</em></p>{/if}
    {#if reaction.notes}
      <details>
        <summary>What {who} was thinking</summary>
        <p class="notes">{reaction.notes}</p>
      </details>
    {/if}
  </section>
{/if}

<style>
  .reaction p { margin: 0; }
  .notes { white-space: pre-wrap; overflow-wrap: anywhere; color: var(--md-sys-color-on-surface-variant); margin-top: 8px; }
</style>
