// The conversation: guess-turn banter from the AIs, and chat between a human and an AI partner.

import { sendChat } from "./api.ts";
import type { Context } from "./context.ts";
import { el } from "./draw.ts";
import type { StateMessage } from "./types.ts";

let chatDraft = "";
let waiting = false;

export function talkView(ctx: Context, state: StateMessage): HTMLElement | null {
  const partner = state.chat_with;
  if (ctx.talk.length === 0 && !partner) return null;
  const name = (seat: string) => state.names[seat] ?? seat;

  const log = el(
    "ul",
    { class: "talk", "aria-label": "Conversation", "aria-live": "polite" },
    ...ctx.talk.slice(-12).map((m) =>
      el(
        "li",
        { class: m.kind },
        el("strong", {}, `${name(m.seat)}: `),
        m.kind === "banter" ? el("em", {}, m.text) : m.text,
      ),
    ),
  );
  const panel = el("section", { class: "card talkcard", "aria-label": "Chat" }, el("h2", {}, "Chat"), log);
  if (ctx.talk.length === 0) log.append(el("li", { class: "hint" }, "Nothing said yet."));
  if (!partner) return panel;

  const input = el("input", {
    id: "chat",
    type: "text",
    autocomplete: "off",
    maxlength: 500,
    value: chatDraft,
    placeholder: `Say something to ${name(partner)}`,
    "aria-label": `Say something to ${name(partner)}`,
  });
  const send = el("button", { type: "submit" }, waiting ? "Waiting…" : "Send");
  const refresh = () => send.toggleAttribute("disabled", waiting || input.value.trim() === "");
  input.addEventListener("input", () => {
    chatDraft = input.value;
    refresh();
  });
  const form = el("form", { class: "row chat" }, input, send);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text || waiting) return;
    waiting = true;
    chatDraft = "";
    ctx.redraw();
    const refused = await sendChat(text);
    waiting = false;
    if (refused) ctx.setNotice(refused);
    else ctx.redraw();
  });
  refresh();
  panel.append(form);
  return panel;
}
