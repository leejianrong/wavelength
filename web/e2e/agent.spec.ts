import { expect, test } from "./fixtures.ts";

test("with no key the agent is the one AI to pick, and the page says it is waiting for it", async ({ page, agentLobby }) => {
  await page.goto(agentLobby.url);
  await page.getByRole("button", { name: "You + an AI partner" }).click();
  const player = page.getByLabel("Player for seat 2");
  await expect(player.locator("option", { hasText: "Custom model" })).toBeDisabled(); // no key for a model
  await expect(page.getByRole("alert")).toContainText("Pick the agent");
  await expect(page.getByRole("button", { name: "Start" })).toBeDisabled();
  await player.selectOption("Claude Code");
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.getByLabel("Rounds").selectOption("3");
  await page.getByRole("button", { name: "Start" }).click();

  await expect(page.getByText(/You are the psychic\. Your target/)).toBeVisible();
  await page.getByLabel("Your clue").fill("a lazy afternoon");
  await page.getByRole("button", { name: "Give clue" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Waiting for the agent in semula" })).toBeVisible();
  await expect(page.locator("body")).not.toContainText("127.0.0.1:"); // the address stays on the server
});
