import type {
  LobbyMessage,
  Move,
  DraftMessage,
  HeardMessage,
  ProblemMessage,
  ReactionMessage,
  StartRequest,
  StateMessage,
  TalkMessage,
  ThinkingMessage,
  VoiceMessage,
} from "./types.ts";

export type Connection = "connecting" | "live" | "lost";

export interface Handlers {
  onLobby(lobby: LobbyMessage): void;
  onState(state: StateMessage): void;
  onTalk(talk: TalkMessage): void;
  onVoice(voice: VoiceMessage): void;
  onDraft(draft: DraftMessage): void;
  onThinking(thinking: ThinkingMessage): void;
  onHeard(heard: HeardMessage): void;
  onReaction(reaction: ReactionMessage): void;
  onProblem(reason: string): void;
  onConnection(state: Connection): void;
}

/** Open the event stream. The browser reconnects by itself and the server replays the present. */
export function connect(handlers: Handlers): () => void {
  const source = new EventSource("/events");
  const on = <T>(name: string, fn: (body: T) => void) =>
    source.addEventListener(name, (e) => fn(JSON.parse((e as MessageEvent<string>).data) as T));
  on<LobbyMessage>("lobby", handlers.onLobby);
  on<StateMessage>("state", handlers.onState);
  on<TalkMessage>("talk", handlers.onTalk);
  on<VoiceMessage>("voice", handlers.onVoice);
  on<DraftMessage>("draft", handlers.onDraft);
  on<ThinkingMessage>("thinking", handlers.onThinking);
  on<HeardMessage>("heard", handlers.onHeard);
  on<ReactionMessage>("reaction", handlers.onReaction);
  on<ProblemMessage>("problem", (p) => handlers.onProblem(p.reason));
  source.onopen = () => handlers.onConnection("live");
  source.onerror = () => handlers.onConnection("lost");
  return () => source.close();
}

/** POST a command. Returns a readable reason if the server refused it outright, or null if it was
 *  accepted. The verdict (a new state, a problem) arrives on the event stream. */
export async function post(path: string, body: unknown = {}): Promise<string | null> {
  let response: Response;
  try {
    response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return "Could not reach the game. Is it still running?";
  }
  if (response.ok) return null;
  try {
    const parsed = (await response.json()) as { error?: string };
    return parsed.error ?? `The game refused that (${response.status}).`;
  } catch {
    return `The game refused that (${response.status}).`;
  }
}

export const postMove = (move: Move) => post("/api/move", move);
export const startMatch = (request: StartRequest) => post("/api/start", request);
export const stopMatch = () => post("/api/stop");
export const setPeek = (on: boolean) => post("/api/peek", { on });
export const postDraft = (value: number) => post("/api/draft", { value });
export const postHeard = (text: string, final: boolean) => post("/api/heard", { text, final });
export const sendChat = (text: string) => post("/api/chat", { text });
