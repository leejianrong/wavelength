// The messages the server sends (docs/web-protocol.md). The observation is whatever the engine's
// `observation_for` returned for the seat being shown; the page draws it and holds no game logic.

export interface Spectrum {
  left: string;
  right: string;
}

export interface Reveal {
  round: number;
  psychic: string;
  spectrum: Spectrum;
  clue: string;
  guess: number;
  target: number;
  points: number;
}

export interface Observation {
  you: string;
  round: number;
  rounds: number;
  phase: "clue" | "guess" | null;
  total_score: number;
  target_score: number;
  history: Reveal[];
  current_players: string[];
  role: "psychic" | "guesser" | null;
  spectrum?: Spectrum;
  clue?: string | null;
  /** Present only when the seat being shown is the psychic (a human psychic, or a spectator who peeked). */
  target?: number;
  instructions: string;
  won?: boolean;
}

export interface Band {
  within: number;
  points: number;
}

export interface Viewer {
  mode: "player" | "spectator";
  peek: boolean;
  peek_allowed: boolean;
}

export interface StateMessage {
  type: "state";
  seat: string;
  players: string[];
  names: Record<string, string>;
  kinds: Record<string, string>;
  viewer: Viewer;
  observation: Observation;
  awaiting: "clue" | "guess" | null;
  clue_limits: { max_words: number | null; max_chars: number | null } | null;
  scoring: Band[];
  chat_with: string | null;
  /** The origin of the vikaki hub whose avatar page is framed, or null when the server runs without voice. */
  voice_hub: string | null;
}

export interface VoiceLine {
  seat: string;
  text: string;
  kind: "clue" | "banter" | "table_talk";
}

/** `none`: the server has no voice; `on`: lines are being spoken; `off`: the hub is unreachable or failed. */
export interface VoiceMessage {
  type: "voice";
  status: "none" | "on" | "off";
  line: VoiceLine | null;
}

export interface LobbyMessage {
  type: "lobby";
  llm_available: boolean;
  default_model: string;
  models: string[];
  /** Named AI players from the server's players file (name and model; never the personality). */
  players: { name: string; model: string }[];
  max_calls: number;
  rounds: number;
  round_options: number[];
}

export interface TalkEntry {
  seat: string;
  text: string;
  kind: "banter" | "chat";
  round: number | null;
}

export interface TalkMessage {
  type: "talk";
  messages: TalkEntry[];
}

export interface ProblemMessage {
  type: "problem";
  reason: string;
}

export type Move = { type: "clue"; text: string } | { type: "guess"; value: number };

export type SeatKind = "human" | "bot" | "llm";

export interface SeatChoice {
  kind: SeatKind;
  model?: string;
  player?: string;
}

export interface StartRequest {
  seats: [SeatChoice, SeatChoice];
  rounds: number;
}
