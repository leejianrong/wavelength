// The messages the server sends (docs/web-protocol.md). The observation is whatever the engine's
// `observation_for` returned for this seat; the page draws it and holds no game logic.

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
  /** Present only when this seat is the psychic. */
  target?: number;
  instructions: string;
  won?: boolean;
}

export interface Band {
  within: number;
  points: number;
}

export interface StateMessage {
  type: "state";
  seat: string;
  players: string[];
  observation: Observation;
  awaiting: "clue" | "guess" | null;
  clue_limits: { max_words: number | null; max_chars: number | null } | null;
  scoring: Band[];
}

export interface ProblemMessage {
  type: "problem";
  reason: string;
}

export type Move = { type: "clue"; text: string } | { type: "guess"; value: number };
