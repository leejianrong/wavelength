// The page's state: what the server last said, and what the person has typed and not yet sent.
// Svelte tracks reads of these objects, so a view redraws exactly when what it shows changes.

import { postDraft, type Connection } from "./api.ts";
import { clampValue } from "./dial.ts";
import type {
  DraftMessage,
  LobbyMessage,
  ReactionMessage,
  StateMessage,
  TalkEntry,
  ThinkingMessage,
  VoiceLine,
  VoiceMessage,
} from "./types.ts";

export const app = $state<{
  state: StateMessage | null;
  lobby: LobbyMessage | null;
  talk: TalkEntry[];
  notice: string;
  connection: Connection;
  voice: { status: VoiceMessage["status"]; line: VoiceLine | null; seats: VoiceMessage["seats"] };
  /** The guesser's needle while they think, as the server last said (public numbers only). */
  needle: DraftMessage | null;
  thinking: ThinkingMessage | null;
  reaction: ReactionMessage | null;
}>({
  state: null,
  lobby: null,
  talk: [],
  notice: "",
  connection: "connecting",
  voice: { status: "none", line: null, seats: null },
  needle: null,
  thinking: null,
  reaction: null,
});

export const draft = $state({
  clue: "",
  guess: 50,
  chat: "",
  submitting: false,
  chatWaiting: false,
  round: "",
  key: "",
});

export const lobbyDraft = $state<{
  kinds: ["human" | "bot" | "llm", "human" | "bot" | "llm"];
  models: [string, string];
  players: [string, string];
  rounds: number;
  ready: boolean;
  starting: boolean;
}>({ kinds: ["human", "llm"], models: ["", ""], players: ["", ""], rounds: 6, ready: false, starting: false });

/** The last round already revealed when this page first saw the match; only later reveals are animated. */
export const seen = $state({ round: -1 });

export function applyLobby(next: LobbyMessage): void {
  seen.round = -1;
  app.lobby = next;
  app.state = null;
  app.talk = [];
  app.notice = "";
  app.voice = { status: "none", line: null, seats: null };
  app.needle = app.thinking = app.reaction = null;
  if (!lobbyDraft.ready) {
    lobbyDraft.ready = true;
    lobbyDraft.models = [next.default_model, next.default_model];
    lobbyDraft.rounds = next.rounds;
    if (!next.llm_available) lobbyDraft.kinds = ["human", "bot"];
  }
}

export function applyState(next: StateMessage): void {
  const obs = next.observation;
  const key = `${obs.round}:${obs.phase}:${next.awaiting}`;
  if (key !== draft.key || app.notice) draft.submitting = false;
  if (key !== draft.key) {
    if (draft.round !== String(obs.round)) draft.clue = "";
    draft.round = String(obs.round);
    draft.key = key;
  }
  if (seen.round < 0) seen.round = obs.history[obs.history.length - 1]?.round ?? 0;
  app.state = next;
  app.lobby = null;
  app.notice = "";
}

/** The server refused a move after accepting the request (the engine's verdict): show why, and let the person try again. */
export function applyProblem(reason: string): void {
  app.notice = reason;
  draft.submitting = false;
}

export function applyVoice(next: VoiceMessage): void {
  app.voice = { status: next.status, line: next.line, seats: next.seats };
}

export function applyDraft(next: DraftMessage): void {
  app.needle = next.value === null ? null : next;
}

export function applyThinking(next: ThinkingMessage): void {
  app.thinking = next;
}

export function applyReaction(next: ReactionMessage): void {
  app.reaction = next;
}

/** Where the other player's needle is, for a page that is not the one moving it. Only during a guess,
 *  and never the human guesser's own (their dial is the one they drag). */
export function watchedNeedle(state: StateMessage): number | undefined {
  const needle = app.needle;
  if (!needle || state.observation.phase !== "guess") return undefined;
  if (state.viewer.mode === "player" && state.observation.role === "guesser") return undefined;
  return needle.value ?? undefined;
}

let lastSent = 0;
let pending: ReturnType<typeof setTimeout> | undefined;
const DRAFT_EVERY_MS = 200;

/** The human guesser moved the needle: show it, and tell the server at most five times a second (the
 *  last position always goes). A draft is only a number to show; the move is the Lock in button. */
export function setGuess(value: number): void {
  draft.guess = clampValue(value);
  const send = () => {
    pending = undefined;
    lastSent = Date.now();
    void postDraft(draft.guess);
  };
  const wait = lastSent + DRAFT_EVERY_MS - Date.now();
  if (wait <= 0) send();
  else if (pending === undefined) pending = setTimeout(send, wait);
}

/** Whether the avatar stage is shown: the server has a hub and it is working. The stage then holds the dial. */
export function staged(state: StateMessage): boolean {
  return state.voice_hub !== null && app.voice.status === "on";
}
