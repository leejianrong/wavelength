// Draws one StateMessage (or the start screen). The page holds no game logic: what it may show is
// whatever the server sent, and what is legal is judged by the engine, not here.

import { postMove, setPeek, stopMatch } from "./api.ts";
import type { Context } from "./context.ts";
import { clampValue, countWords } from "./dial.ts";
import { dial } from "./dialview.ts";
import { el } from "./draw.ts";
import { lobbyView } from "./lobby.ts";
import { talkView } from "./talk.ts";
import type { Band, Reveal, Spectrum, StateMessage } from "./types.ts";

export type { Context } from "./context.ts";

// What the person has typed or chosen and not yet sent; kept across redraws.
const draft = { key: "", clue: "", guess: 50 };
let submitting = false;
let lastKey = "";

const nameOf = (state: StateMessage, seat: string) => state.names[seat] ?? seat;

function revealCard(reveal: Reveal, bands: Band[], state: StateMessage): HTMLElement {
  const who = nameOf(state, reveal.psychic);
  const d = dial({ spectrum: reveal.spectrum, bands, target: reveal.target, guess: reveal.guess });
  return el(
    "section",
    { class: "card reveal", "aria-label": `Round ${reveal.round} result` },
    el("h2", {}, `Round ${reveal.round} result`),
    d.svg,
    el(
      "p",
      { class: "result" },
      el("strong", {}, `${reveal.points} point${reveal.points === 1 ? "" : "s"}`),
      ` · ${who} said "${reveal.clue}" · target ${reveal.target} out of 100, guess ${reveal.guess}`,
    ),
  );
}

function clueForm(ctx: Context, state: StateMessage): HTMLElement {
  const limits = state.clue_limits;
  const maxWords = limits?.max_words ?? null;
  const input = el("input", {
    id: "clue",
    type: "text",
    autocomplete: "off",
    maxlength: limits?.max_chars ?? 80,
    value: draft.clue,
    "aria-describedby": "clue-help",
  });
  const counter = el("span", { id: "clue-help", class: "hint" });
  const send = el("button", { type: "submit", class: "primary" }, "Give clue");
  const refresh = () => {
    const words = countWords(input.value);
    counter.textContent = maxWords ? `${words} / ${maxWords} words` : `${words} words`;
    send.toggleAttribute("disabled", submitting || input.value.trim() === "");
  };
  input.addEventListener("input", () => {
    draft.clue = input.value;
    refresh();
  });
  const form = el("form", { class: "row" }, el("label", { for: "clue" }, "Your clue"), input, send, counter);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (submitting || input.value.trim() === "") return;
    submitting = true;
    refresh();
    const problem = await postMove({ type: "clue", text: input.value });
    if (problem) {
      submitting = false;
      ctx.setNotice(problem);
    }
  });
  refresh();
  return form;
}

function guessForm(ctx: Context, state: StateMessage): HTMLElement {
  const spectrum = state.observation.spectrum as Spectrum;
  const readout = el("output", { id: "guess-value", for: "guess" }, String(draft.guess));
  const slider = el("input", {
    id: "guess",
    type: "range",
    min: 0,
    max: 100,
    step: 1,
    value: draft.guess,
    "aria-label": `Your guess from 0 (${spectrum.left}) to 100 (${spectrum.right})`,
  });
  const send = el("button", { type: "submit", class: "primary" }, `Lock in ${draft.guess}`);
  const d = dial({ spectrum, guess: draft.guess, onGuess: (value) => set(value) });
  function set(value: number) {
    draft.guess = clampValue(value);
    slider.value = String(draft.guess);
    readout.textContent = String(draft.guess);
    send.textContent = `Lock in ${draft.guess}`;
    d.setGuess(draft.guess);
  }
  slider.addEventListener("input", () => set(Number(slider.value)));
  send.toggleAttribute("disabled", submitting);
  const form = el("form", { class: "guess" }, d.svg, slider, el("div", { class: "row" }, readout, send));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (submitting) return;
    submitting = true;
    send.setAttribute("disabled", "");
    const problem = await postMove({ type: "guess", value: draft.guess });
    if (problem) {
      submitting = false;
      ctx.setNotice(problem);
    }
  });
  return form;
}

/** A human playing: they are the psychic (and see the target) or the guesser. */
function playPanel(ctx: Context, state: StateMessage): HTMLElement {
  const obs = state.observation;
  const spectrum = obs.spectrum as Spectrum;
  const partner = state.players.find((p) => p !== obs.you) ?? "";
  const other = nameOf(state, partner);
  const panel = el("section", { class: "card round", "aria-label": `Round ${obs.round}` });
  panel.append(el("h2", {}, `Round ${obs.round} of ${obs.rounds}`));
  if (obs.role === "psychic") {
    panel.append(
      el("p", {}, `You are the psychic. Your target: ${obs.target} out of 100.`),
      dial({ spectrum, bands: state.scoring, target: obs.target }).svg,
    );
    if (state.awaiting === "clue") panel.append(clueForm(ctx, state));
    else panel.append(el("p", { class: "waiting" }, `Your clue: "${obs.clue}". ${other} is guessing…`));
  } else if (state.awaiting === "guess") {
    panel.append(el("p", { class: "clue" }, "The clue: ", el("q", {}, obs.clue ?? "")), guessForm(ctx, state));
  } else {
    panel.append(
      el("p", {}, "You are the guesser."),
      dial({ spectrum }).svg,
      el("p", { class: "waiting" }, `${other} is thinking of a clue…`),
    );
  }
  return panel;
}

/** Two AIs playing and a person watching. The default view is the guesser's (no target); a peek adds it. */
function watchPanel(state: StateMessage): HTMLElement {
  const obs = state.observation;
  const spectrum = obs.spectrum as Spectrum;
  const viewed = obs.you;
  const other = state.players.find((p) => p !== viewed) ?? viewed;
  const guesser = obs.role === "guesser" ? viewed : other;
  const psychic = obs.role === "psychic" ? viewed : other;
  const panel = el("section", { class: "card round", "aria-label": `Round ${obs.round}` });
  panel.append(
    el("h2", {}, `Round ${obs.round} of ${obs.rounds}`),
    el("p", {}, `${nameOf(state, psychic)} is the psychic, ${nameOf(state, guesser)} is the guesser.`),
    dial({ spectrum, bands: obs.target === undefined ? undefined : state.scoring, target: obs.target }).svg,
  );
  if (obs.target !== undefined) panel.append(el("p", { class: "hint" }, `Peeking: the target is ${obs.target} out of 100.`));
  panel.append(
    obs.phase === "clue"
      ? el("p", { class: "waiting" }, `${nameOf(state, psychic)} is thinking of a clue…`)
      : el(
          "p",
          { class: "waiting" },
          "The clue: ",
          el("q", {}, obs.clue ?? ""),
          ` — ${nameOf(state, guesser)} is guessing…`,
        ),
  );
  const toggle = el(
    "button",
    { type: "button", id: "peek", "aria-pressed": state.viewer.peek },
    state.viewer.peek ? "Stop peeking" : "Peek at the target",
  );
  toggle.addEventListener("click", async () => {
    await setPeek(!state.viewer.peek);
  });
  panel.append(el("p", { class: "hint" }, "Peeking shows the target and spoils the guess."), toggle);
  return panel;
}

function recap(state: StateMessage): HTMLElement {
  const obs = state.observation;
  const rows = obs.history.map((r) =>
    el(
      "tr",
      {},
      el("td", {}, String(r.round)),
      el("td", {}, nameOf(state, r.psychic)),
      el("td", {}, r.clue),
      el("td", {}, String(r.guess)),
      el("td", {}, String(r.target)),
      el("td", {}, String(r.points)),
    ),
  );
  const again = el("button", { type: "button", class: "primary" }, "New match");
  again.addEventListener("click", () => void stopMatch());
  const spectator = state.viewer.mode === "spectator";
  const verdict = obs.won
    ? spectator ? "The team reached the goal" : "You won!"
    : spectator ? "The team did not reach the goal" : "You did not reach the goal";
  return el(
    "section",
    { class: "card recap" },
    el("h2", {}, verdict),
    el("p", { class: "result" }, `${obs.total_score} of ${obs.target_score} points.`),
    el(
      "div",
      { class: "table-wrap" },
      el(
        "table",
        {},
        el(
          "thead",
          {},
          el("tr", {}, ...["Round", "Psychic", "Clue", "Guess", "Target", "Points"].map((h) => el("th", {}, h))),
        ),
        el("tbody", {}, ...rows),
      ),
    ),
    again,
  );
}

export function render(root: HTMLElement, ctx: Context): void {
  const focused = document.activeElement instanceof HTMLElement ? document.activeElement.id : "";
  const { state } = ctx;
  root.replaceChildren();

  if (!state) {
    root.append(el("header", {}, el("h1", {}, "Wavelength")));
    if (ctx.notice) root.append(el("p", { class: "problem", role: "alert" }, ctx.notice));
    if (ctx.lobby) root.append(lobbyView(ctx, ctx.lobby));
    else {
      root.append(
        el("p", { role: "status" }, ctx.connection === "lost" ? "Cannot reach the game." : "Connecting…"),
      );
    }
    if (focused) document.getElementById(focused)?.focus();
    return;
  }

  const obs = state.observation;
  const key = `${obs.round}:${obs.phase}:${state.awaiting}`;
  if (key !== lastKey || ctx.notice) submitting = false;
  if (key !== lastKey) {
    lastKey = key;
    if (draft.key.split(":")[0] !== String(obs.round)) draft.clue = "";
    draft.key = key;
  }

  const over = obs.phase === null;
  const end = el("button", { type: "button", class: "quiet" }, over ? "New match" : "End match");
  end.addEventListener("click", () => void stopMatch());
  root.append(
    el(
      "header",
      {},
      el("h1", {}, "Wavelength"),
      el(
        "p",
        { class: "score", "aria-label": "Score" },
        over ? "Match over" : `Round ${obs.round} of ${obs.rounds}`,
        ` · ${obs.total_score} / ${obs.target_score} points`,
      ),
    ),
  );
  if (!over) root.append(el("div", { class: "toolbar" }, end));
  if (ctx.connection === "lost") {
    root.append(el("p", { class: "banner", role: "status" }, "Connection lost. Trying to reconnect…"));
  }
  if (ctx.notice) root.append(el("p", { class: "problem", role: "alert" }, ctx.notice));

  // What to do comes first, so the dial and the form never sit below the fold; the last result follows.
  const spectator = state.viewer.mode === "spectator";
  root.append(over ? recap(state) : spectator ? watchPanel(state) : playPanel(ctx, state));
  const latest = obs.history[obs.history.length - 1];
  if (latest) root.append(revealCard(latest, state.scoring, state));
  const talk = talkView(ctx, state);
  if (talk) root.append(talk);
  root.append(el("details", { class: "how" }, el("summary", {}, "How to play"), el("p", {}, obs.instructions)));

  if (focused) document.getElementById(focused)?.focus();
}
