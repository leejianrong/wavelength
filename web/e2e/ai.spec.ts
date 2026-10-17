import { expect, test } from "./fixtures.ts";

const CLUE = "a lazy afternoon";

test("a person can play with an AI partner, chat with it, and start again", async ({ page, lobby }) => {
  await page.goto(lobby.url);
  await expect(page.getByRole("heading", { name: "Who is playing?" })).toBeVisible();
  await page.getByRole("button", { name: "You + an AI partner" }).click();
  await page.getByLabel("Rounds").selectOption("3");
  await page.getByRole("button", { name: "Start" }).click();

  // Round 1: you are the psychic; the AI is the guesser, so it can chat.
  await expect(page.getByText(/You are the psychic\. Your target: \d+ out of 100\./)).toBeVisible();
  await page.getByLabel("Say something to deepseek-v4.1-flash").fill("what do you make of this?");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByRole("list", { name: "Conversation" })).toContainText("mocked chat reply");

  await page.getByLabel("Your clue").fill(CLUE);
  await page.getByRole("button", { name: "Give clue" }).click();
  // The AI's guess comes with its banter, shown in the conversation.
  await expect(page.getByRole("list", { name: "Conversation" })).toContainText("mocked banter");

  // Round 2: you guess the AI's clue.
  await expect(page.getByText("The clue:")).toBeVisible();
  await page.getByRole("button", { name: /Lock in/ }).click();
  await expect(page.getByLabel("Your clue")).toBeVisible(); // round 3, psychic again
  await page.getByLabel("Your clue").fill(CLUE);
  await page.getByRole("button", { name: "Give clue" }).click();

  await expect(page.locator("section.recap")).toBeVisible();
  await expect(page.locator("section.recap tbody tr")).toHaveCount(3);
  await page.getByRole("button", { name: "New match" }).first().click();
  await expect(page.getByRole("heading", { name: "Who is playing?" })).toBeVisible();
});

test("an AI psychic will not discuss the round, and the guesser's page never holds the target", async ({
  page,
  lobby,
}) => {
  await page.goto(lobby.url);
  await page.getByLabel("Seat 1", { exact: true }).selectOption("llm");
  await page.getByLabel("Seat 2", { exact: true }).selectOption("human");
  await page.getByLabel("Rounds").selectOption("3");
  await page.getByRole("button", { name: "Start" }).click();

  // Round 1: the AI is the psychic and the human guesses.
  await expect(page.getByText("The clue:")).toBeVisible();
  await page.getByLabel("Say something to deepseek-v4.1-flash").fill("is it near the left end?");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByRole("list", { name: "Conversation" })).toContainText("I'm the psychic this round");
  await expect(page.locator("section.round svg .target")).toHaveCount(0);
  expect(await page.locator("section.round").innerHTML()).not.toContain("target");
});

test("two AIs can be watched; the target stays hidden unless you peek", async ({ page, slowLobby }) => {
  await page.goto(slowLobby.url);
  await page.getByRole("button", { name: "Watch two AIs" }).click();
  await page.getByLabel("Rounds").selectOption("3");
  await page.getByRole("button", { name: "Start" }).click();

  const round = page.locator("section.round");
  await expect(round).toContainText("is the psychic");
  await expect(round.locator("svg .target")).toHaveCount(0); // the default view is the guesser's
  expect(await round.innerHTML()).not.toContain("Peeking: the target");

  await page.getByRole("button", { name: "Peek at the target" }).click();
  await expect(round.locator("svg .target")).toHaveCount(1);
  await expect(round).toContainText("Peeking: the target is");
  await page.getByRole("button", { name: "Stop peeking" }).click();
  await expect(round.locator("svg .target")).toHaveCount(0);
  await expect(round).not.toContainText("Peeking: the target is");

  await expect(page.locator("section.recap")).toBeVisible({ timeout: 45_000 });
  await expect(page.locator("section.recap tbody tr")).toHaveCount(3);
});

test("a match can be ended and the start screen comes back", async ({ page, slowLobby }) => {
  await page.goto(slowLobby.url);
  await page.getByRole("button", { name: "Watch two AIs" }).click();
  await page.getByRole("button", { name: "Start" }).click();
  await expect(page.locator("section.round")).toBeVisible();
  await page.getByRole("button", { name: "End match" }).click();
  await expect(page.getByRole("heading", { name: "Who is playing?" })).toBeVisible();
  await expect(page.locator("section.round")).toHaveCount(0);
});

test("without an OpenRouter key the AI choices are off and say why", async ({ page, lobbyNoKey }) => {
  await page.goto(lobbyNoKey.url);
  await expect(page.getByRole("button", { name: "Watch two AIs" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "You + an AI partner" })).toBeDisabled();
  await expect(page.getByText("no OpenRouter key was set")).toBeVisible();
  await page.getByRole("button", { name: "You + the bot" }).click();
  await page.getByRole("button", { name: "Start" }).click();
  await expect(page.getByText(/You are the psychic\. Your target: \d+ out of 100\./)).toBeVisible();
});

test("two humans cannot be chosen", async ({ page, lobbyNoKey }) => {
  await page.goto(lobbyNoKey.url);
  await page.getByLabel("Seat 2", { exact: true }).selectOption("human");
  await expect(page.getByRole("alert")).toContainText("Only one human");
  await expect(page.getByRole("button", { name: "Start" })).toBeDisabled();
});

test.describe("on a phone", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("the start screen and a watched match fit the screen", async ({ page, slowLobby }) => {
    await page.goto(slowLobby.url);
    await expect(page.getByRole("heading", { name: "Who is playing?" })).toBeVisible();
    const sideways = () => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(await sideways()).toBeLessThanOrEqual(0);
    await page.getByRole("button", { name: "Watch two AIs" }).click();
    await page.getByRole("button", { name: "Start" }).click();
    await expect(page.locator("section.round")).toBeVisible();
    expect(await sideways()).toBeLessThanOrEqual(0);
    await page.getByRole("button", { name: "End match" }).click();
  });
});
