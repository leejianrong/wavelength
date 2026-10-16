import type { Move, ProblemMessage, StateMessage } from "./types.ts";

export type Connection = "connecting" | "live" | "lost";

export interface Handlers {
  onState(state: StateMessage): void;
  onProblem(reason: string): void;
  onConnection(state: Connection): void;
}

/** Open the event stream. The browser reconnects by itself and the server re-sends the current state. */
export function connect(handlers: Handlers): () => void {
  const source = new EventSource("/events");
  source.addEventListener("state", (e) => handlers.onState(JSON.parse((e as MessageEvent<string>).data) as StateMessage));
  source.addEventListener("problem", (e) => {
    const body = JSON.parse((e as MessageEvent<string>).data) as ProblemMessage;
    handlers.onProblem(body.reason);
  });
  source.onopen = () => handlers.onConnection("live");
  source.onerror = () => handlers.onConnection("lost");
  return () => source.close();
}

/** Send a move. Returns a readable reason if the server refused it outright, or null if it was accepted.
 *  The engine's verdict (a new state, or a problem) arrives on the event stream. */
export async function postMove(move: Move): Promise<string | null> {
  let response: Response;
  try {
    response = await fetch("/api/move", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(move),
    });
  } catch {
    return "Could not reach the game. Is it still running?";
  }
  if (response.ok) return null;
  try {
    const body = (await response.json()) as { error?: string };
    return body.error ?? `The game refused that (${response.status}).`;
  } catch {
    return `The game refused that (${response.status}).`;
  }
}
