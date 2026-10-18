// The browser's speech recogniser, behind one small seam (ADR-0013). Chrome's `webkitSpeechRecognition`
// sends the audio to Google; the page says so. Where there is none (Firefox) `createRecogniser` is null
// and typing is the only way. Whatever recognises, the rest of the page only sees text and whether it is final.

interface Alternative {
  transcript: string;
}
interface ResultLike {
  isFinal: boolean;
  0: Alternative;
}
interface ResultEvent {
  resultIndex: number;
  results: ArrayLike<ResultLike>;
}
interface RecogLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((e: ResultEvent) => void) | null;
  onend: (() => void) | null;
  onerror: ((e: { error?: string }) => void) | null;
  start(): void;
  stop(): void;
}
type RecogCtor = new () => RecogLike;

export interface RecogniserHandlers {
  /** A partial (`final` false) or finished line of text. */
  onText(text: string, final: boolean): void;
  /** The recogniser stopped, by `stop()` or by itself; `reason` says why when it was an error. */
  onStop(reason?: string): void;
}

export interface Recogniser {
  start(): void;
  stop(): void;
}

function ctor(): RecogCtor | null {
  const w = window as unknown as { SpeechRecognition?: RecogCtor; webkitSpeechRecognition?: RecogCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export const recogniserAvailable = (): boolean => ctor() !== null;

/** The readable reason for a recogniser error code, or null when it is not worth showing. */
export function errorReason(code: string | undefined): string | null {
  switch (code) {
    case "no-speech":
    case "aborted":
      return null;
    case "not-allowed":
    case "service-not-allowed":
      return "The microphone is blocked. Allow it for this page in the browser's address bar.";
    case "audio-capture":
      return "No microphone was found.";
    case "network":
      return "The browser's speech service could not be reached.";
    default:
      return "The microphone stopped working.";
  }
}

/** Pull the text out of a result event: finished lines each as final, the unfinished rest as one partial. */
export function readResults(e: ResultEvent): { text: string; final: boolean }[] {
  const out: { text: string; final: boolean }[] = [];
  let partial = "";
  for (let i = e.resultIndex; i < e.results.length; i++) {
    const result = e.results[i];
    const text = result?.[0].transcript.trim();
    if (!result || !text) continue;
    if (result.isFinal) out.push({ text, final: true });
    else partial = `${partial} ${text}`.trim();
  }
  if (partial) out.push({ text: partial, final: false });
  return out;
}

export function createRecogniser(handlers: RecogniserHandlers, lang = navigator.language || "en-US"): Recogniser | null {
  const Ctor = ctor();
  if (!Ctor) return null;
  const recog = new Ctor();
  recog.lang = lang;
  recog.continuous = true;
  recog.interimResults = true;
  let reason: string | undefined;
  recog.onresult = (e) => {
    for (const r of readResults(e)) handlers.onText(r.text, r.final);
  };
  recog.onerror = (e) => {
    reason = e.error;
  };
  recog.onend = () => {
    const why = reason;
    reason = undefined;
    handlers.onStop(why);
  };
  return { start: () => recog.start(), stop: () => recog.stop() };
}
