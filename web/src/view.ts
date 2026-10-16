// Draws one StateMessage. The page holds no game logic: what it may show is whatever the server sent
// for this seat, and what is legal is judged by the engine, not here.

import { postMove, type Connection } from "./api.ts";
import { arcPath, bandArcs, clampValue, countWords, pointToValue, polar } from "./dial.ts";
import type { Band, Reveal, Spectrum, StateMessage } from "./types.ts";

export interface Context {
  state: StateMessage | null;
  notice: string;
  connection: Connection;
  setNotice(text: string): void;
}

const SVG_NS = "http://www.w3.org/2000/svg";
const CX = 200;
const CY = 190;
const R_OUT = 170;
const R_IN = 105;

// What the person has typed or chosen and not yet sent; kept across redraws.
const draft = { key: "", clue: "", guess: 50 };
let submitting = false;
let lastKey = "";

type Child = Node | string | null | false;

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  props: Record<string, string | boolean | number> = {},
  ...children: Child[]
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(props)) {
    if (value === false) continue;
    node.setAttribute(name, value === true ? "" : String(value));
  }
  for (const child of children) if (child) node.append(child);
  return node;
}

function svg<K extends keyof SVGElementTagNameMap>(
  tag: K,
  attrs: Record<string, string | number>,
  parent?: SVGElement,
): SVGElementTagNameMap[K] {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, String(value));
  parent?.append(node);
  return node;
}

interface DialOptions {
  spectrum: Spectrum;
  bands?: Band[];
  target?: number;
  guess?: number;
  onGuess?: (value: number) => void;
}

function dial(opts: DialOptions): { svg: SVGSVGElement; setGuess(value: number): void } {
  const root = svg("svg", {
    viewBox: "0 0 400 235",
    class: opts.onGuess ? "dial interactive" : "dial",
    role: "img",
    "aria-label": `Dial from ${opts.spectrum.left} to ${opts.spectrum.right}`,
  });
  svg("path", { d: arcPath(CX, CY, R_IN, R_OUT, 0, 100), class: "track" }, root);
  if (opts.target !== undefined && opts.bands) {
    for (const arc of bandArcs(opts.target, opts.bands)) {
      svg("path", { d: arcPath(CX, CY, R_IN, R_OUT, arc.from, arc.to), class: `band band-${arc.points}` }, root);
    }
  }
  if (opts.target !== undefined) {
    const a = polar(CX, CY, R_IN - 8, opts.target);
    const b = polar(CX, CY, R_OUT + 10, opts.target);
    svg("line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y, class: "target" }, root);
  }
  svg("text", { x: CX - R_OUT, y: CY + 32, class: "end start" }, root).textContent = opts.spectrum.left;
  svg("text", { x: CX + R_OUT, y: CY + 32, class: "end finish" }, root).textContent = opts.spectrum.right;

  const needle = svg("g", { class: "needle" }, root);
  const line = svg("line", { x1: CX, y1: CY, x2: CX, y2: CY, class: "needle-line" }, needle);
  const knob = svg("circle", { cx: CX, cy: CY, r: 9, class: "knob" }, needle);
  if (opts.guess !== undefined) svg("circle", { cx: CX, cy: CY, r: 7, class: "hub" }, root);
  const setGuess = (value: number) => {
    const tip = polar(CX, CY, R_OUT - 6, value);
    line.setAttribute("x2", String(tip.x));
    line.setAttribute("y2", String(tip.y));
    const k = polar(CX, CY, R_OUT - 6, value);
    knob.setAttribute("cx", String(k.x));
    knob.setAttribute("cy", String(k.y));
    needle.setAttribute("visibility", "visible");
  };
  if (opts.guess === undefined) needle.setAttribute("visibility", "hidden");
  else setGuess(opts.guess);

  if (opts.onGuess) {
    const onGuess = opts.onGuess;
    root.style.touchAction = "none";
    let dragging = false;
    const move = (e: PointerEvent) => {
      const ctm = root.getScreenCTM();
      if (!ctm) return;
      const pt = root.createSVGPoint();
      pt.x = e.clientX;
      pt.y = e.clientY;
      const local = pt.matrixTransform(ctm.inverse());
      onGuess(pointToValue(local.x, local.y, CX, CY));
    };
    root.addEventListener("pointerdown", (e) => {
      dragging = true;
      root.setPointerCapture(e.pointerId);
      move(e);
    });
    root.addEventListener("pointermove", (e) => dragging && move(e));
    root.addEventListener("pointerup", () => (dragging = false));
    root.addEventListener("pointercancel", () => (dragging = false));
  }
  return { svg: root, setGuess };
}

function revealCard(reveal: Reveal, bands: Band[], opponent: string, you: string): HTMLElement {
  const who = reveal.psychic === you ? "You" : opponent;
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
      ` · ${who} said "${reveal.clue}" · target ${reveal.target}, guess ${reveal.guess}`,
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
  const form = el(
    "form",
    { class: "row" },
    el("label", { for: "clue" }, "Your clue"),
    input,
    send,
    counter,
  );
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
  const d = dial({
    spectrum,
    guess: draft.guess,
    onGuess: (value) => set(value),
  });
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

function roundPanel(ctx: Context, state: StateMessage, opponent: string): HTMLElement {
  const obs = state.observation;
  const spectrum = obs.spectrum as Spectrum;
  const panel = el("section", { class: "card round", "aria-label": `Round ${obs.round}` });
  panel.append(el("h2", {}, `Round ${obs.round} of ${obs.rounds}`));
  if (obs.role === "psychic") {
    panel.append(
      el("p", {}, `You are the psychic. The target is ${obs.target}.`),
      dial({ spectrum, bands: state.scoring, target: obs.target }).svg,
    );
    if (state.awaiting === "clue") panel.append(clueForm(ctx, state));
    else panel.append(el("p", { class: "waiting" }, `Your clue: "${obs.clue}". ${opponent} is guessing…`));
  } else if (state.awaiting === "guess") {
    panel.append(el("p", { class: "clue" }, "The clue: ", el("q", {}, obs.clue ?? "")), guessForm(ctx, state));
  } else {
    panel.append(
      el("p", {}, "You are the guesser."),
      dial({ spectrum }).svg,
      el("p", { class: "waiting" }, `${opponent} is thinking of a clue…`),
    );
  }
  return panel;
}

function recap(state: StateMessage, opponent: string): HTMLElement {
  const obs = state.observation;
  const rows = obs.history.map((r) =>
    el(
      "tr",
      {},
      el("td", {}, String(r.round)),
      el("td", {}, r.psychic === obs.you ? "You" : opponent),
      el("td", {}, r.clue),
      el("td", {}, String(r.guess)),
      el("td", {}, String(r.target)),
      el("td", {}, String(r.points)),
    ),
  );
  const again = el("button", { type: "button", class: "primary" }, "Play again");
  again.addEventListener("click", () => location.reload());
  return el(
    "section",
    { class: "card recap" },
    el("h2", {}, obs.won ? "You won!" : "You did not reach the goal"),
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
    root.append(
      el("h1", {}, "Wavelength"),
      el("p", { role: "status" }, ctx.connection === "lost" ? "Cannot reach the game." : "Connecting…"),
    );
    return;
  }
  const obs = state.observation;
  const opponent = state.players.find((p) => p !== obs.you) ?? "your partner";
  const key = `${obs.round}:${obs.phase}:${state.awaiting}`;
  if (key !== lastKey || ctx.notice) submitting = false;
  if (key !== lastKey) {
    lastKey = key;
    if (draft.key.split(":")[0] !== String(obs.round)) draft.clue = "";
    draft.key = key;
  }

  root.append(
    el(
      "header",
      {},
      el("h1", {}, "Wavelength"),
      el(
        "p",
        { class: "score", "aria-label": "Score" },
        obs.phase === null ? "Match over" : `Round ${obs.round} of ${obs.rounds}`,
        ` · ${obs.total_score} / ${obs.target_score} points`,
      ),
    ),
  );
  if (ctx.connection === "lost") {
    root.append(el("p", { class: "banner", role: "status" }, "Connection lost. Trying to reconnect…"));
  }
  if (ctx.notice) root.append(el("p", { class: "problem", role: "alert" }, ctx.notice));

  // What to do comes first, so the dial and the form never sit below the fold; the last result follows.
  root.append(obs.phase === null ? recap(state, opponent) : roundPanel(ctx, state, opponent));
  const latest = obs.history[obs.history.length - 1];
  if (latest) root.append(revealCard(latest, state.scoring, opponent, obs.you));
  root.append(
    el("details", { class: "how" }, el("summary", {}, "How to play"), el("p", {}, obs.instructions)),
  );

  if (focused) document.getElementById(focused)?.focus();
}
