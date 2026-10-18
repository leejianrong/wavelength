import { expect, test } from "./fixtures.ts";

test("a human guesser's needle is sent to the server as drafts, and Lock in is still the move", async ({ page, game }) => {
  await page.goto(game.url);
  // Round 1: you are the psychic and the bot guesses; round 2: you guess.
  await page.getByLabel("Your clue").fill("a lazy afternoon");
  await page.getByRole("button", { name: "Give clue" }).click();
  const slider = page.getByRole("slider");
  await expect(slider).toBeVisible();

  const drafted = page.waitForRequest((r) => r.url().endsWith("/api/draft") && r.method() === "POST");
  await slider.fill("73");
  const request = await drafted;
  expect(request.postDataJSON()).toEqual({ value: 73 });

  // A draft is not a move: the guess form is still there until you lock in.
  await expect(page.getByRole("button", { name: "Lock in 73" })).toBeVisible();
  await page.getByRole("button", { name: "Lock in 73" }).click();
  await expect(page.locator("section.reveal").last()).toContainText("guess 73");
});

test("watching two AIs: the needle moves, the guesser's thoughts show, and the psychic reacts after the reveal", async ({
  page,
  slowLobby,
}) => {
  await page.goto(slowLobby.url);
  await page.getByRole("button", { name: "Watch two AIs" }).click();
  await page.getByLabel("Rounds").selectOption("3");
  await page.getByRole("button", { name: "Start" }).click();

  // The guesser's thoughts, as a line under the dial (the mock's notes are its plain-call reply).
  const thinking = page.getByLabel("Thinking");
  await expect(thinking).toContainText("is thinking:", { timeout: 20_000 });
  await expect(thinking).toContainText("mocked chat reply");

  // The needle is not still: it takes more than one position before the reveal.
  const needle = page.locator("section.round g.needle");
  const seen = new Set<string>();
  const until = Date.now() + 4000;
  while (Date.now() < until) {
    const style = await needle.getAttribute("style", { timeout: 500 }).catch(() => null);
    if (style) seen.add(style);
    await page.waitForTimeout(100);
  }
  expect(seen.size).toBeGreaterThan(1);

  // After a reveal the psychic reacts, and what it was thinking is folded away until asked for.
  const reaction = page.locator("section.reaction").first();
  await expect(reaction).toBeVisible({ timeout: 30_000 });
  await expect(reaction).toContainText("mocked chat reply");
  const notes = reaction.locator("details");
  await expect(notes).not.toHaveAttribute("open", "");
  await notes.locator("summary").click();
  await expect(notes).toHaveAttribute("open", "");
});

test("a psychic's reaction and notes are on the page only for a round that has been revealed", async ({
  page,
  slowLobby,
}) => {
  await page.goto(slowLobby.url);
  await page.getByRole("button", { name: "Watch two AIs" }).click();
  await page.getByLabel("Rounds").selectOption("3");
  await page.getByRole("button", { name: "Start" }).click();
  await expect(page.getByLabel("Thinking")).toBeVisible({ timeout: 20_000 });
  const until = Date.now() + 8000;
  while (Date.now() < until) {
    const reactions = await page.locator("section.reaction").count();
    const reveals = await page.locator("section.reveal").count();
    expect(reactions).toBeLessThanOrEqual(reveals);
    // and the psychic's notes are never in the thinking line, which is the guesser's
    expect(await page.getByLabel("Thinking").count()).toBeLessThanOrEqual(1);
    await page.waitForTimeout(50);
  }
});

test("an AI guesser works the needle in steps: each line is listed, and the needle ends where it locked", async ({
  page,
  stepsLobby,
}) => {
  await page.goto(stepsLobby.url);
  await page.getByRole("button", { name: "Watch two AIs" }).click();
  await page.getByLabel("Rounds").selectOption("3");
  await page.getByRole("button", { name: "Start" }).click();

  const thinking = page.getByLabel("Thinking");
  await expect(thinking.locator("li")).toHaveCount(2, { timeout: 20_000 });
  await expect(thinking.locator("li").first()).toContainText("mocked step one");
  await expect(thinking.locator("li").last()).toContainText("mocked step two");
  // The needle is at the mocked lock (62 on a 0-100 half dial = 111.6 degrees) before the reveal.
  await expect(page.locator("section.round g.needle")).toHaveAttribute("style", /rotate\(111\.6/);
  // The list starts again for the next round.
  await expect(page.locator("section.reveal").first()).toBeVisible({ timeout: 30_000 });
});
