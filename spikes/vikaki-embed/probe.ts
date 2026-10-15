// Spike probe: serves host.html on its own port, loads it in Chromium, and records what the avatar page does when the
// game page that embeds it clicks (or does not), with and without allow="autoplay". Run with VIKAKI_DIR set (see README).
import { createRequire } from "node:module";
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const vik = process.env.VIKAKI_DIR!;
const req = createRequire(join(vik, "packages/e2e/package.json"));
const { chromium } = req("playwright") as typeof import("playwright");
const { transformSync } = req("esbuild") as typeof import("esbuild");

const HOST_PORT = 8890;
const server = createServer((rq, rs) => {
  const path = (rq.url ?? "/").split("?")[0];
  if (path === "/host.js") {
    rs.setHeader("content-type", "text/javascript");
    rs.end(transformSync(readFileSync(join(here, "host.ts"), "utf8"), { loader: "ts" }).code);
  } else {
    rs.setHeader("content-type", "text/html");
    rs.end(readFileSync(join(here, "host.html")));
  }
});
await new Promise<void>((r) => server.listen(HOST_PORT, "127.0.0.1", r));

const variants = [
  { name: "no click, allow=autoplay", allow: "autoplay", click: "none" },
  { name: "click parent button, allow=autoplay", allow: "autoplay", click: "parent" },
  { name: "click parent button, no allow attr", allow: "none", click: "parent" },
  { name: "click inside the iframe, allow=autoplay", allow: "autoplay", click: "inside" },
  { name: "click inside the iframe, no allow attr", allow: "none", click: "inside" },
];
const browser = await chromium.launch({ headless: true, channel: "chromium", args: ["--autoplay-policy=document-user-activation-required"] });
for (const v of variants) {
  const ctx = await browser.newContext({ viewport: { width: 1200, height: 560 } });
  await ctx.addInitScript(() => {
    const W = window as unknown as { __ctxs: AudioContext[]; AudioContext: typeof AudioContext };
    W.__ctxs = [];
    const Orig = W.AudioContext;
    W.AudioContext = class extends Orig {
      constructor(...a: ConstructorParameters<typeof AudioContext>) {
        super(...a);
        W.__ctxs.push(this);
      }
    } as typeof AudioContext;
  });
  const page = await ctx.newPage();
  await page.goto(`http://127.0.0.1:${HOST_PORT}/?allow=${v.allow}&seats=2`);
  const frame = page.frames().find((f) => f !== page.mainFrame())!;
  await frame.waitForFunction(() => (window as unknown as { __vikaki?: { ready: boolean } }).__vikaki?.ready === true, undefined, { timeout: 30000 }).catch(() => {});
  const ready = await frame.evaluate(() => (window as unknown as { __vikaki?: { ready: boolean } }).__vikaki?.ready ?? null);
  if (v.click === "parent") await page.click("#sound");
  if (v.click === "inside") await page.mouse.click(300, 250);
  const spoken = execFileSync("uv", ["run", "--with", join(vik, "clients/python"), "python", join(here, "drive.py"), "--only", "first"], { encoding: "utf8" });
  const states = await frame.evaluate(() => (window as unknown as { __ctxs: AudioContext[] }).__ctxs.map((c) => c.state));
  console.log(`\n## ${v.name}\npage ready: ${ready}; AudioContext states after speech: ${JSON.stringify(states)}\n${spoken.trim()}`);
  if (v.name.startsWith("click parent button, allow=autoplay")) await page.screenshot({ path: join(here, "embed.png") });
  await ctx.close();
}
await browser.close();
server.close();
