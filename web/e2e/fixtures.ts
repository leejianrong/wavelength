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
export function targetsFor(seed: number, rounds: number): number[] {
  const code =
    "import json,sys;from wavelength.engine import WavelengthEngine as E;" +
    `s=E().initial_state(['you','bot'],{'rounds':${rounds},'seed':${seed}});` +
    "print(json.dumps([p.target for p in s.plan]))";
  return JSON.parse(execFileSync("uv", ["run", "python", "-c", code], { cwd: repo, encoding: "utf8" })) as number[];
}

export interface Game {
  url: string;
  seed: number;
  rounds: number;
}

export const test = base.extend<{ game: Game }>({
  game: async ({}, use) => {
    const port = await freePort();
    const seed = 7;
    const rounds = 2;
    const server: ChildProcess = spawn(
      "uv",
      ["run", "wavelength", "web", "--port", String(port), "--bot-delay", "0", "--seed", String(seed), "--rounds", String(rounds)],
      { cwd: repo, stdio: "ignore" },
    );
    const url = `http://127.0.0.1:${port}`;
    const deadline = Date.now() + 30_000;
    for (;;) {
      try {
        if ((await fetch(`${url}/api/health`)).ok) break;
      } catch {
        // not up yet
      }
      if (Date.now() > deadline) throw new Error("the game server did not start");
      await new Promise((r) => setTimeout(r, 200));
    }
    await use({ url, seed, rounds });
    server.kill();
  },
});

export { expect };
