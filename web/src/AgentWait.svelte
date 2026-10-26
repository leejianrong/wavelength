<script lang="ts">
  // Shown beside "X is thinking" when X is an agent answering through semula: the wait is a person
  // or a Claude Code session, not a model, so say so and say when the move gives up.
  import type { StateMessage } from "./types.ts";

  let { state, seat }: { state: StateMessage; seat: string } = $props();
  const wait = $derived(state.agents[seat]);
</script>

{#if wait !== undefined}
  <p class="hint" role="status">
    Waiting for the agent in semula. The move gives up after {Math.round(wait)} seconds.
  </p>
{/if}
