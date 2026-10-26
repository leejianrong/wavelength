<script lang="ts">
  // The start screen: who plays. Nothing here knows the rules; the server validates the request.
  import { startMatch } from "./api.ts";
  import { app, lobbyDraft as d } from "./store.svelte.ts";
  import type { LobbyMessage, SeatChoice, SeatKind } from "./types.ts";

  let { lobby }: { lobby: LobbyMessage } = $props();

  const PRESETS: { label: string; seats: [SeatKind, SeatKind] }[] = [
    { label: "You + an AI partner", seats: ["human", "llm"] },
    { label: "Watch two AIs", seats: ["llm", "llm"] },
    { label: "You + the bot", seats: ["human", "bot"] },
  ];
  const KIND_LABEL: Record<SeatKind, string> = { human: "You", bot: "Bot", llm: "AI" };

  const usable = (kind: SeatKind) => kind !== "llm" || lobby.llm_available || lobby.agent_available;
  const isAgent = (name: string | undefined) => lobby.players.some((p) => p.name === name && p.agent);
  const llmSeats = $derived([0, 1].filter((i) => d.kinds[i] === "llm"));
  const problem = $derived(
    d.kinds.filter((k) => k === "human").length > 1
      ? "Only one human can play at a time."
      : llmSeats.filter((i) => isAgent(d.players[i])).length > 1
        ? "Only one agent can play at a time."
        : !lobby.llm_available && llmSeats.some((i) => !isAgent(d.players[i]))
          ? lobby.agent_available
            ? "Pick the agent: other AI players need an OpenRouter key."
            : "AI seats need an OpenRouter key: set OPENROUTER_API_KEY and restart."
          : "",
  );

  function seat(i: 0 | 1): SeatChoice {
    if (d.kinds[i] !== "llm") return { kind: d.kinds[i] };
    return d.players[i]
      ? { kind: "llm", player: d.players[i] }
      : { kind: "llm", model: d.models[i] || lobby.default_model };
  }

  async function submit(e: SubmitEvent) {
    e.preventDefault();
    if (problem || d.starting) return;
    d.starting = true;
    const refused = await startMatch({ seats: [seat(0), seat(1)], rounds: d.rounds });
    d.starting = false;
    if (refused) app.notice = refused;
  }
</script>

<section class="card raised">
  <form class="lobby" onsubmit={submit}>
    <h2>Who is playing?</h2>
    <div class="row" role="group" aria-label="Quick choices">
      {#each PRESETS as p}
        {@const current = p.seats[0] === d.kinds[0] && p.seats[1] === d.kinds[1]}
        <button
          type="button"
          class="chip"
          aria-pressed={current}
          disabled={p.seats.some((k) => !usable(k))}
          onclick={() => (d.kinds = [...p.seats])}
        >{p.label}</button>
      {/each}
    </div>

    <div class="seats">
      {#each [0, 1] as const as i}
        <div class="field">
          <label for="seat-{i}">Seat {i + 1}</label>
          <select id="seat-{i}" aria-label="Seat {i + 1}" bind:value={d.kinds[i]}>
            {#each ["human", "bot", "llm"] as const as kind}
              <option value={kind} disabled={!usable(kind)}>{KIND_LABEL[kind]}</option>
            {/each}
          </select>
          {#if d.kinds[i] === "llm" && (lobby.players.length > 0 || !lobby.llm_available)}
            <select id="player-{i}" aria-label="Player for seat {i + 1}" bind:value={d.players[i]}>
              <option value="" disabled={!lobby.llm_available}>Custom model</option>
              {#each lobby.players as p}
                <option value={p.name} disabled={!p.agent && !lobby.llm_available}>
                  {p.agent ? `${p.name} (agent)` : `${p.name} (${p.model.split("/").pop()})`}
                </option>
              {/each}
            </select>
          {/if}
          {#if d.kinds[i] === "llm" && !d.players[i]}
            <input
              id="model-{i}"
              type="text"
              list="models"
              autocomplete="off"
              aria-label="Model for seat {i + 1}"
              bind:value={d.models[i]}
            />
          {/if}
        </div>
      {/each}
    </div>
    <datalist id="models">{#each lobby.models as m}<option value={m}></option>{/each}</datalist>

    <div class="row">
      <select id="rounds" aria-label="Rounds" class="narrow" bind:value={d.rounds}>
        {#each lobby.round_options as n}<option value={n}>{n} rounds</option>{/each}
      </select>
      <button type="submit" class="btn btn-filled" disabled={problem !== "" || d.starting}>
        {d.starting ? "Starting…" : "Start"}
      </button>
    </div>
    {#if problem}<p class="problem" role="alert">{problem}</p>{/if}
    {#if lobby.agent_available}
      <p class="hint">
        An agent answers each move through semula: it is as slow as the agent, and a move waits
        for it. Start the agent first.
      </p>
    {/if}
    <p class="hint">
      {lobby.llm_available
        ? `An AI seat calls OpenRouter with your key. Each match is capped at ${lobby.max_calls} model calls.`
        : lobby.agent_available
          ? "Models are off: no OpenRouter key was set when the server started."
          : "AI seats are off: no OpenRouter key was set when the server started."}
    </p>
  </form>
</section>

<style>
  .lobby { display: grid; gap: 16px; }
  .seats { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; }
  .field { align-content: start; }
  .narrow { width: auto; }
</style>
