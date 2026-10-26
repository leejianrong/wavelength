import { test as base, expect } from "@playwright/test";
import { execFileSync, spawn, type ChildProcess } from "node:child_process";
import { createServer } from "node:net";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const repo = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const s = createServer();
    s.once("error", reject);
    s.listen(0, "127.0.0.1", () => {
      const { port } = s.address() as { port: number };
      s.close(() => resolve(port));
    });
  });
}

/** The round targets for a seed, from the engine itself (never read by the page under test). */
export function targetsFor(seed: number, rounds: number, players: string[] = ["you", "bot"]): number[] {
  const code =
    "import json,sys;from wavelength.engine import WavelengthEngine as E;" +
    `s=E().initial_state(${JSON.stringify(players)},{'rounds':${rounds},'seed':${seed}});` +
    "print(json.dumps([p.target for p in s.plan]))";
  return JSON.parse(execFileSync("uv", ["run", "python", "-c", code], { cwd: repo, encoding: "utf8" })) as number[];
}

async function waitFor(url: string, what: string): Promise<void> {
  const deadline = Date.now() + 30_000;
  for (;;) {
    try {
      if ((await fetch(url)).ok) return;
    } catch {
      // not up yet
    }
    if (Date.now() > deadline) throw new Error(`${what} did not start`);
    await new Promise((r) => setTimeout(r, 200));
  }
}

async function startServer(args: string[], env: Record<string, string> = {}): Promise<{ url: string; stop(): void }> {
  const port = await freePort();
  const server: ChildProcess = spawn(
    "uv",
    // The needle's walk is off unless a test asks for it: it adds seconds to every AI guess.
    ["run", "wavelength", "web", "--port", String(port), "--bot-delay", "0", ...(args.includes("--walk-pause") ? [] : ["--walk-pause", "0"]), ...(args.includes("--needle-steps") ? [] : ["--no-needle-steps"]), ...args],
    // No ambient key may leak into a test: AI seats are on only when a test asks for them.
    { cwd: repo, stdio: "ignore", env: { ...process.env, OPENROUTER_API_KEY: "", ...env } },
  );
  const url = `http://127.0.0.1:${port}`;
  await waitFor(`${url}/api/health`, "the game server");
  return { url, stop: () => void server.kill() };
}

/** A stand-in OpenRouter: answers every move legally (a fixed clue, the middle guess) and chats back. */
async function startMock(delay: number): Promise<{ url: string; stop(): void }> {
  const proc: ChildProcess = spawn("uv", ["run", "python", "tests/e2e/_mock_openrouter.py", "--delay", String(delay)], {
    cwd: repo,
    stdio: ["ignore", "pipe", "ignore"],
  });
  const url = await new Promise<string>((resolve, reject) => {
    proc.stdout!.once("data", (chunk: Buffer) => resolve(String(chunk).trim()));
    proc.once("exit", () => reject(new Error("the mock OpenRouter exited")));
    setTimeout(() => reject(new Error("the mock OpenRouter did not start")), 30_000);
  });
  return { url, stop: () => void proc.kill() };
}

/** A stand-in vikaki hub (tests/e2e/_stub_hub.py): its avatar page and driver socket on one port. */
async function startStubHub(speak: number): Promise<{ url: string; stop(): void }> {
  const proc: ChildProcess = spawn("uv", ["run", "python", "tests/e2e/_stub_hub.py", "--speak", String(speak)], {
    cwd: repo,
    stdio: ["ignore", "pipe", "ignore"],
  });
  const url = await new Promise<string>((resolve, reject) => {
    proc.stdout!.once("data", (chunk: Buffer) => resolve(String(chunk).trim()));
    proc.once("exit", () => reject(new Error("the stub hub exited")));
    setTimeout(() => reject(new Error("the stub hub did not start")), 30_000);
  });
  return { url, stop: () => void proc.kill() };
}

export interface Game {
  url: string;
  seed: number;
  rounds: number;
}

export interface Lobby {
  url: string;
}

export const test = base.extend<{ game: Game; lobby: Lobby; lobbyNoKey: Lobby; slowLobby: Lobby; stepsLobby: Lobby; playersLobby: Lobby; agentLobby: Lobby; voiceGame: Game & { hub: string }; deadHubGame: Game }>({
  // A human against the scripted bot, started from the command line (no start screen).
  game: async ({}, use) => {
    const seed = 7;
    const rounds = 2;
    const server = await startServer(["--seat", "human", "--seat", "bot:wl-random", "--seed", String(seed), "--rounds", String(rounds)]);
    await use({ url: server.url, seed, rounds });
    server.stop();
  },
  // The start screen, with a mocked AI behind it.
  lobby: async ({}, use) => {
    const mock = await startMock(0);
    const server = await startServer([], { OPENROUTER_API_KEY: "test-key", OPENROUTER_BASE_URL: mock.url });
    await use({ url: server.url });
    server.stop();
    mock.stop();
  },
  // The same, but each AI move takes half a second, so a watched match stays open long enough to act on.
  slowLobby: async ({}, use) => {
    const mock = await startMock(0.5);
    const server = await startServer(["--walk-pause", "0.6"], { OPENROUTER_API_KEY: "test-key", OPENROUTER_BASE_URL: mock.url });
    await use({ url: server.url });
    server.stop();
    mock.stop();
  },
  // The same, with an AI guesser that works the needle in steps (V15); the mock answers each step at once.
  stepsLobby: async ({}, use) => {
    const mock = await startMock(0.3);
    const server = await startServer(["--needle-steps", "--walk-pause", "0.6"], {
      OPENROUTER_API_KEY: "test-key",
      OPENROUTER_BASE_URL: mock.url,
    });
    await use({ url: server.url });
    server.stop();
    mock.stop();
  },
  // The start screen with named players loaded from the example file, and a mocked AI.
  playersLobby: async ({}, use) => {
    const mock = await startMock(0.5);
    const server = await startServer(["--players", "players.example.toml"], {
      OPENROUTER_API_KEY: "test-key",
      OPENROUTER_BASE_URL: mock.url,
    });
    await use({ url: server.url });
    server.stop();
    mock.stop();
  },
  // The start screen with an agent as the only AI and no OpenRouter key: the mock stands in for semula,
  // and takes 1.5 seconds a move so the page's waiting hint can be seen.
  agentLobby: async ({}, use) => {
    const mock = await startMock(1.5);
    const server = await startServer(["--semula", mock.url]);
    await use({ url: server.url });
    server.stop();
    mock.stop();
  },
  // A human against the bot with voice on: the avatar page and the drivers' socket are a stub hub.
  voiceGame: async ({}, use) => {
    const hub = await startStubHub(1.0);
    const seed = 7;
    const rounds = 2;
    const server = await startServer([
      "--voice", "fake", "--hub", hub.url,
      "--seat", "human", "--seat", "bot:wl-random", "--seed", String(seed), "--rounds", String(rounds),
    ]);
    await use({ url: server.url, seed, rounds, hub: hub.url });
    server.stop();
    hub.stop();
  },
  // Voice asked for, but nothing listens at the hub address: the game must stay a text game.
  deadHubGame: async ({}, use) => {
    const seed = 7;
    const rounds = 2;
    const server = await startServer([
      "--voice", "fake", "--hub", `http://127.0.0.1:${await freePort()}`,
      "--seat", "human", "--seat", "bot:wl-random", "--seed", String(seed), "--rounds", String(rounds),
    ]);
    await use({ url: server.url, seed, rounds });
    server.stop();
  },
  // The start screen with no OpenRouter key.
  lobbyNoKey: async ({}, use) => {
    const server = await startServer([]);
    await use({ url: server.url });
    server.stop();
  },
});

export { expect };

/** A stand-in for Chrome's recogniser, as plain script (an init script is not transpiled), so a test can
 *  speak: `window.__speech.say(text, final)`. */
export const fakeRecogniser = `
  class Fake {
    constructor() { this.lang = ""; this.continuous = false; this.interimResults = false; this.onresult = null; this.onend = null; this.onerror = null; }
    start() { window.__speech = this; }
    stop() { if (this.onend) this.onend(); }
    say(text, isFinal) {
      const result = Object.assign([{ transcript: text }], { isFinal });
      if (this.onresult) this.onresult({ resultIndex: 0, results: [result] });
    }
  }
  window.webkitSpeechRecognition = Fake;
  window.SpeechRecognition = Fake;
`;
