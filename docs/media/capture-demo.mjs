import { createRequire } from "node:module";
import fs from "node:fs";
const require = createRequire("/home/jianlee/projects/games/agent-games/wavelength/web/");
const { chromium } = require("@playwright/test");
const OUT = process.argv[2];
const URL = "http://127.0.0.1:8765/";
const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1280, height: 720 },
  recordVideo: { dir: `${OUT}/rec`, size: { width: 1280, height: 720 } },
});
const page = await context.newPage();
const cues = [];
const captions = [];
const started = Date.now();
const now = () => (Date.now() - started) / 1000;
const cue = (sfx) => cues.push({ sfx, t: +now().toFixed(2) });
const log = (m) => console.log(now().toFixed(1), m);

await page.goto(URL);
await page.getByRole("heading", { name: "Who is playing?" }).waitFor();
await page.screenshot({ path: `${OUT}/start.png` });
await page.waitForTimeout(1500);
await page.getByLabel("Seat 1", { exact: true }).selectOption("llm");
await page.getByLabel("Seat 2", { exact: true }).selectOption("llm");
await page.getByLabel("Player for seat 1").selectOption("Bright Optimist");
await page.getByLabel("Player for seat 2").selectOption("Dry Sceptic");
await page.waitForTimeout(1200);
await page.getByRole("button", { name: "Start" }).click();
cue("click");
const tClick = now();
log("started");
await page.locator("section.stage iframe").waitFor();
const t0 = now();
captions.push({ text: "Two AIs, one dial", start: +(t0 + 0.5).toFixed(1), end: +(t0 + 4).toFixed(1) });
// The clue is spoken: wait for the first subtitle line.
await page.locator(".captions .line strong").first().waitFor({ timeout: 90000 });
log("clue subtitle");
const tClue = now();
await page.screenshot({ path: `${OUT}/desktop-clue.png` });
// A phone-sized view of the same match.
const phone = await browser.newContext({ viewport: { width: 390, height: 844 } });
const pp = await phone.newPage();
await pp.goto(URL);
await pp.locator("section.stage iframe").waitFor();
await pp.waitForTimeout(2500);
await pp.screenshot({ path: `${OUT}/phone-stage.png` });
await phone.close();
// The first reveal.
await page.getByRole("heading", { name: /Round 1 result/ }).waitFor({ timeout: 120000 });
cue("pop");
log("reveal 1");
const tReveal = now();
await page.waitForTimeout(2200);
cue("success-chime");
await page.screenshot({ path: `${OUT}/desktop-reveal.png` });
const t1 = now();
captions.push({ text: "Roles swap every round", start: +(t1 + 0.5).toFixed(1), end: +(t1 + 3.5).toFixed(1) });
await page.locator(".captions .line strong").first().waitFor({ timeout: 90000 }).catch(() => {});
await page.waitForTimeout(5000);
log("end");
const total = now();
const video = page.video();
await context.close();
fs.writeFileSync(`${OUT}/marks.json`, JSON.stringify({ tClick, tClue, tReveal, total }));
fs.writeFileSync(`${OUT}/cues.json`, JSON.stringify(cues, null, 2));
fs.writeFileSync(`${OUT}/captions.json`, JSON.stringify(captions, null, 2));
console.log("video", await video.path(), "seconds", total.toFixed(1));
await browser.close();
