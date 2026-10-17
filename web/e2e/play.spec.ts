import { expect, targetsFor, test } from "./fixtures.ts";

const CLUE = "a lazy afternoon";

test("a whole match can be played with the mouse and keyboard", async ({ page, game }) => {
  await page.goto(game.url);

  // Round 1: the human is the psychic and sees the target.
  await expect(page.getByRole("heading", { name: "Round 1 of 2" })).toBeVisible();
  await expect(page.getByText(/You are the psychic\. Your target: \d+ out of 100\./)).toBeVisible();
  await page.getByLabel("Your clue").fill(CLUE);
  await expect(page.getByText("3 / 6 words")).toBeVisible();
  await page.getByRole("button", { name: "Give clue" }).click();

  // The bot guesses, round 1 is revealed, and the human now guesses round 2.
  await expect(page.getByRole("region", { name: "Round 1 result" })).toContainText(`You said "${CLUE}"`);
  await expect(page.getByRole("heading", { name: "Round 2 of 2" })).toBeVisible();
  await expect(page.getByText("The clue:")).toBeVisible();

  // Dragging the dial moves the guess; the slider does the same by keyboard.
  const dial = page.locator("svg.dial.interactive");
  await dial.scrollIntoViewIfNeeded();
  const box = (await dial.boundingBox())!;
  await page.mouse.click(box.x + box.width * 0.75, box.y + box.height * 0.45);
  const afterClick = Number(await page.locator("#guess-value").textContent());
  expect(afterClick).toBeGreaterThan(50);
  await page.locator("#guess").focus();
  await page.keyboard.press("ArrowLeft");
  await expect(page.locator("#guess-value")).toHaveText(String(afterClick - 1));
  await page.getByRole("button", { name: /Lock in/ }).click();

  // The recap lists both rounds.
  await expect(page.getByText("Match over")).toBeVisible();
  await expect(page.locator("section.recap tbody tr")).toHaveCount(2);
  await expect(page.getByRole("button", { name: "New match" })).toBeVisible();
});

test("a clue the rules reject shows the reason and can be corrected", async ({ page, game }) => {
  await page.goto(game.url);
  await page.getByLabel("Your clue").fill("about 70");
  await page.getByRole("button", { name: "Give clue" }).click();
  await expect(page.getByRole("alert")).toContainText("digits");
  await expect(page.getByLabel("Your clue")).toBeVisible();
  await page.getByLabel("Your clue").fill(CLUE);
  await page.getByRole("button", { name: "Give clue" }).click();
  await expect(page.getByRole("heading", { name: "Round 2 of 2" })).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("a reload mid-match shows the same round, not a new game", async ({ page, game }) => {
  await page.goto(game.url);
  await page.getByLabel("Your clue").fill(CLUE);
  await page.getByRole("button", { name: "Give clue" }).click();
  await expect(page.getByRole("heading", { name: "Round 2 of 2" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Round 2 of 2" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Round 1 result" })).toBeVisible();
});

test("the guesser's page never shows the target before the reveal", async ({ page, game }) => {
  const targets = targetsFor(game.seed, game.rounds);
  await page.goto(game.url);
  await expect(page.locator("svg .target")).toHaveCount(1); // the psychic sees a target marker
  await page.getByLabel("Your clue").fill(CLUE);
  await page.getByRole("button", { name: "Give clue" }).click();
  await expect(page.getByText("The clue:")).toBeVisible();

  // Round 2, human guessing: no target marker, no target text, anywhere in the page.
  await expect(page.locator("svg.dial.interactive .target")).toHaveCount(0);
  const text = await page.locator("main").innerText();
  expect(text).not.toMatch(new RegExp(`target\\s+(is\\s+)?${targets[1]}\\b`, "i"));
  const revealOnly = await page.locator("section.round").innerHTML();
  expect(revealOnly).not.toContain("target");
});

test.describe("on a phone", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("the page fits the screen without sideways scrolling", async ({ page, game }) => {
    await page.goto(game.url);
    await page.getByLabel("Your clue").fill(CLUE);
    await page.getByRole("button", { name: "Give clue" }).click();
    await expect(page.getByText("The clue:")).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
    await page.getByRole("button", { name: /Lock in/ }).click();
    await expect(page.locator("section.recap")).toBeVisible();
    // The recap table must fit too (it once forced the card wider than the screen).
    const card = (await page.locator("section.recap").boundingBox())!;
    expect(card.x + card.width).toBeLessThanOrEqual(390);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
  });
});
