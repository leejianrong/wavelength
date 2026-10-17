// The page's state: what the server last said, and what the person has typed and not yet sent.
// Svelte tracks reads of these objects, so a view redraws exactly when what it shows changes.

import type { Connection } from "./api.ts";
import type { LobbyMessage, StateMessage, TalkEntry } from "./types.ts";

export const app = $state<{
  state: StateMessage | null;
  lobby: LobbyMessage | null;
  talk: TalkEntry[];
  notice: string;
  connection: Connection;
}>({ state: null, lobby: null, talk: [], notice: "", connection: "connecting" });

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

export function applyLobby(next: LobbyMessage): void {
  app.lobby = next;
  app.state = null;
  app.talk = [];
  app.notice = "";
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
  app.state = next;
  app.lobby = null;
  app.notice = "";
}

/** The server refused a move after accepting the request (the engine's verdict): show why, and let the person try again. */
export function applyProblem(reason: string): void {
  app.notice = reason;
  draft.submitting = false;
}
