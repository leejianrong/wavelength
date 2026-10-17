<script lang="ts">
  import { stopMatch } from "./api.ts";
  import Lobby from "./Lobby.svelte";
  import Play from "./Play.svelte";
  import Recap from "./Recap.svelte";
  import Reveal from "./Reveal.svelte";
  import { app } from "./store.svelte.ts";
  import Talk from "./Talk.svelte";
  import Watch from "./Watch.svelte";

  const state = $derived(app.state);
  const obs = $derived(state?.observation);
  const over = $derived(obs?.phase === null);
  const latest = $derived(obs?.history[obs.history.length - 1]);
</script>

<main>
  <header>
    <h1>Wavelength</h1>
    {#if obs}
      <p class="score" aria-label="Score">
        {over ? "Match over" : `Round ${obs.round} of ${obs.rounds}`} · {obs.total_score} / {obs.target_score} points
      </p>
    {/if}
  </header>

  {#if state && obs}
    {#if !over}
      <div class="toolbar">
        <button type="button" class="btn btn-text" onclick={() => void stopMatch()}>End match</button>
      </div>
    {/if}
    {#if app.connection === "lost"}
      <p class="banner" role="status">Connection lost. Trying to reconnect…</p>
    {/if}
    {#if app.notice}
      <p class="problem" role="alert">{app.notice}</p>
    {/if}

    <!-- What to do comes first, so the dial and the form never sit below the fold; the last result follows. -->
    {#if over}
      <Recap {state} />
    {:else if state.viewer.mode === "spectator"}
      <Watch {state} />
    {:else}
      <Play {state} />
    {/if}
    {#if latest}
      <Reveal reveal={latest} {state} />
    {/if}
    <Talk {state} />
    <details class="how">
      <summary>How to play</summary>
      <p>{obs.instructions}</p>
    </details>
  {:else}
    {#if app.notice}
      <p class="problem" role="alert">{app.notice}</p>
    {/if}
    {#if app.lobby}
      <Lobby lobby={app.lobby} />
    {:else}
      <p role="status">{app.connection === "lost" ? "Cannot reach the game." : "Connecting…"}</p>
    {/if}
  {/if}
</main>

<style>
  main { max-width: 680px; margin: 0 auto; padding: 16px; display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; }
  header { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 4px 16px; }
  .score { color: var(--md-sys-color-on-surface-variant); font-variant-numeric: tabular-nums; }
  .toolbar { display: flex; justify-content: flex-end; margin-top: -8px; }
  .how { color: var(--md-sys-color-on-surface-variant); }
  .how summary { cursor: pointer; }
</style>
