// The start screen: who plays. Nothing here knows the rules; the server validates the request.

import { startMatch } from "./api.ts";
import type { Context } from "./context.ts";
import { el } from "./draw.ts";
import type { LobbyMessage, SeatChoice, SeatKind } from "./types.ts";

const PRESETS: { label: string; seats: [SeatKind, SeatKind] }[] = [
  { label: "You + an AI partner", seats: ["human", "llm"] },
  { label: "Watch two AIs", seats: ["llm", "llm"] },
  { label: "You + the bot", seats: ["human", "bot"] },
];

const KIND_LABEL: Record<SeatKind, string> = { human: "You", bot: "Bot", llm: "AI" };

const draft: { kinds: [SeatKind, SeatKind]; models: [string, string]; players: [string, string]; rounds: number; ready: boolean } = {
  kinds: ["human", "llm"],
  models: ["", ""],
  players: ["", ""],
  rounds: 6,
  ready: false,
};
let starting = false;

function initDraft(lobby: LobbyMessage) {
  if (draft.ready) return;
  draft.ready = true;
  draft.models = [lobby.default_model, lobby.default_model];
  draft.rounds = lobby.rounds;
  if (!lobby.llm_available) draft.kinds = ["human", "bot"];
}

export function lobbyView(ctx: Context, lobby: LobbyMessage): HTMLElement {
  initDraft(lobby);
  const usable = (kind: SeatKind) => kind !== "llm" || lobby.llm_available;
  const humans = draft.kinds.filter((k) => k === "human").length;
  const problem =
    humans > 1
      ? "Only one human can play at a time."
      : draft.kinds.some((k) => !usable(k))
        ? "AI seats need an OpenRouter key: set OPENROUTER_API_KEY and restart."
        : "";

  const presets = el(
    "div",
    { class: "presets", role: "group", "aria-label": "Quick choices" },
    ...PRESETS.map((p) => {
      const current = p.seats[0] === draft.kinds[0] && p.seats[1] === draft.kinds[1];
      const button = el("button", { type: "button", "aria-pressed": current, class: current ? "chosen" : "" }, p.label);
      if (p.seats.some((k) => !usable(k))) button.setAttribute("disabled", "");
      button.addEventListener("click", () => {
        draft.kinds = [...p.seats];
        ctx.redraw();
      });
      return button;
    }),
  );

  const seatBox = (index: 0 | 1): HTMLElement => {
    const select = el("select", { id: `seat-${index}`, "aria-label": `Seat ${index + 1}` });
    for (const kind of ["human", "bot", "llm"] as SeatKind[]) {
      const option = el("option", { value: kind }, KIND_LABEL[kind]);
      if (draft.kinds[index] === kind) option.setAttribute("selected", "");
      if (!usable(kind)) option.setAttribute("disabled", "");
      select.append(option);
    }
    select.addEventListener("change", () => {
      draft.kinds[index] = select.value as SeatKind;
      ctx.redraw();
    });
    const box = el("div", { class: "seat" }, el("label", { for: `seat-${index}` }, `Seat ${index + 1}`), select);
    if (draft.kinds[index] === "llm" && lobby.players.length > 0) {
      const player = el("select", { id: `player-${index}`, "aria-label": `Player for seat ${index + 1}` });
      player.append(el("option", { value: "" }, "Custom model"));
      for (const p of lobby.players) {
        const option = el("option", { value: p.name }, `${p.name} (${p.model.split("/").pop()})`);
        if (draft.players[index] === p.name) option.setAttribute("selected", "");
        player.append(option);
      }
      player.addEventListener("change", () => {
        draft.players[index] = player.value;
        ctx.redraw();
      });
      box.append(player);
    }
    if (draft.kinds[index] === "llm" && !draft.players[index]) {
      const model = el("input", {
        id: `model-${index}`,
        type: "text",
        list: "models",
        value: draft.models[index],
        autocomplete: "off",
        "aria-label": `Model for seat ${index + 1}`,
      });
      model.addEventListener("input", () => (draft.models[index] = model.value.trim()));
      box.append(model);
    }
    return box;
  };

  const rounds = el("select", { id: "rounds", "aria-label": "Rounds" });
  for (const n of lobby.round_options) {
    const option = el("option", { value: n }, `${n} rounds`);
    if (n === draft.rounds) option.setAttribute("selected", "");
    rounds.append(option);
  }
  rounds.addEventListener("change", () => (draft.rounds = Number(rounds.value)));

  const start = el("button", { type: "submit", class: "primary" }, starting ? "Starting…" : "Start");
  if (problem || starting) start.setAttribute("disabled", "");
  const form = el(
    "form",
    { class: "lobby" },
    el("h2", {}, "Who is playing?"),
    presets,
    el("div", { class: "seats" }, seatBox(0), seatBox(1)),
    el("datalist", { id: "models" }, ...lobby.models.map((m) => el("option", { value: m }))),
    el("div", { class: "row" }, rounds, start),
    problem ? el("p", { class: "problem", role: "alert" }, problem) : false,
    el(
      "p",
      { class: "hint" },
      lobby.llm_available
        ? `An AI seat calls OpenRouter with your key. Each match is capped at ${lobby.max_calls} model calls.`
        : "AI seats are off: no OpenRouter key was set when the server started.",
    ),
  );
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (problem || starting) return;
    starting = true;
    ctx.redraw();
    const seat = (i: 0 | 1): SeatChoice =>
      draft.kinds[i] !== "llm"
        ? { kind: draft.kinds[i] }
        : draft.players[i]
          ? { kind: "llm", player: draft.players[i] }
          : { kind: "llm", model: draft.models[i] || lobby.default_model };
    const refused = await startMatch({ seats: [seat(0), seat(1)], rounds: draft.rounds });
    starting = false;
    if (refused) ctx.setNotice(refused);
    else ctx.redraw();
  });
  return el("section", { class: "card" }, form);
}
