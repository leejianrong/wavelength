<script lang="ts">
  import { stopMatch } from "./api.ts";
  import type { StateMessage } from "./types.ts";

  let { state }: { state: StateMessage } = $props();
  const obs = $derived(state.observation);
  const spectator = $derived(state.viewer.mode === "spectator");
  const verdict = $derived(
    obs.won
      ? spectator ? "The team reached the goal" : "You won!"
      : spectator ? "The team did not reach the goal" : "You did not reach the goal",
  );
</script>

<section class="card raised recap">
  <h2>{verdict}</h2>
  <p class="result">{obs.total_score} of {obs.target_score} points.</p>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>{#each ["Round", "Psychic", "Clue", "Guess", "Target", "Points"] as h}<th>{h}</th>{/each}</tr>
      </thead>
      <tbody>
        {#each obs.history as r (r.round)}
          <tr>
            <td>{r.round}</td>
            <td>{state.names[r.psychic] ?? r.psychic}</td>
            <td>{r.clue}</td>
            <td>{r.guess}</td>
            <td>{r.target}</td>
            <td>{r.points}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  <div><button type="button" class="btn btn-filled" onclick={() => void stopMatch()}>New match</button></div>
</section>

<style>
  .table-wrap { overflow-x: auto; }
</style>
