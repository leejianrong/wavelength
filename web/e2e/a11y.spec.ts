import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures.ts";

// Automated checks (axe, WCAG 2 A and AA including colour contrast) on every screen, in both colour schemes.
async function clean(page: Page, screen: string) {
  const { violations } = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(
    violations.map((v) => `${screen}: ${v.id} ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`),
  ).toEqual([]);
}

for (const scheme of ["light", "dark"] as const) {
  test.describe(`${scheme} scheme`, () => {
    test.use({ colorScheme: scheme });

    test("the start screen has no accessibility violations", async ({ page, lobby }) => {
      await page.goto(lobby.url);
      await expect(page.getByRole("heading", { name: "Who is playing?" })).toBeVisible();
      await clean(page, "start");
    });

    test("every screen of a match has no accessibility violations", async ({ page, game }) => {
      await page.goto(game.url);
      await expect(page.getByLabel("Your clue")).toBeVisible();
      await clean(page, "psychic turn");
      await page.getByLabel("Your clue").fill("a lazy afternoon");
      await page.getByRole("button", { name: "Give clue" }).click();
      await expect(page.locator("#guess")).toBeVisible();
      await clean(page, "guess turn with a result");
      await page.getByRole("button", { name: /Lock in/ }).click();
      await expect(page.locator("section.recap")).toBeVisible();
      await clean(page, "recap");
    });
  });
}

const status = (page: Page) => page.locator('.sr-only[role="status"]');

test("a new turn moves focus to its field and is announced, without the hidden target", async ({ page, game }) => {
  await page.goto(game.url);
  await expect(page.getByLabel("Your clue")).toBeFocused();
  await expect(status(page)).toHaveText("Round 1: your turn, give a clue.");
  await page.getByLabel("Your clue").fill("a lazy afternoon");
  await page.getByRole("button", { name: "Give clue" }).click();
  await expect(page.locator("#guess")).toBeFocused();
  await expect(status(page)).toContainText("Round 1 result:");
  await expect(status(page)).toContainText("Round 2: your turn, guess from 0 to 100.");
});

test("a reveal that arrives live is staged, and a reload shows it at rest", async ({ page, game }) => {
  await page.goto(game.url);
  await page.getByLabel("Your clue").fill("a lazy afternoon");
  await page.getByRole("button", { name: "Give clue" }).click();
  const reveal = page.locator("section.reveal");
  await expect(reveal.locator(".points.staged")).toBeVisible(); // the points land after the needle settles
  await expect(reveal.locator("svg .target")).toHaveCount(1);
  await page.reload();
  await expect(reveal.locator(".points")).toBeVisible();
  await expect(reveal.locator(".points.staged")).toHaveCount(0);
});

test.describe("with reduced motion", () => {
  test.use({ reducedMotion: "reduce" });
  test("the reveal is shown at once, not staged", async ({ page, game }) => {
    await page.goto(game.url);
    await page.getByLabel("Your clue").fill("a lazy afternoon");
    await page.getByRole("button", { name: "Give clue" }).click();
    const reveal = page.locator("section.reveal");
    await expect(reveal.locator(".points")).toBeVisible();
    await expect(reveal.locator(".points.staged")).toHaveCount(0);
  });
});
