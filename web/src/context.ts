import type { Connection } from "./api.ts";
import type { LobbyMessage, StateMessage, TalkEntry } from "./types.ts";

/** Everything a view may draw from, plus the two ways it can ask to be redrawn. */
export interface Context {
  state: StateMessage | null;
  lobby: LobbyMessage | null;
  talk: TalkEntry[];
  notice: string;
  connection: Connection;
  setNotice(text: string): void;
  redraw(): void;
}
