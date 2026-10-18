import { expect, fakeRecogniser, test } from "./fixtures.ts";

const say = (page: import("@playwright/test").Page, text: string, final: boolean) =>
  page.evaluate(([t, f]) => (window as never as { __speech: { say(t: string, f: boolean): void } }).__speech.say(t as string, f as boolean), [text, final]);

test.describe("with a recogniser", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript({ content: fakeRecogniser });
  });

  test("a spoken clue fills the clue box, is not sent anywhere, and still needs Give clue", async ({ page, game }) => {
    const heard: string[] = [];
    page.on("request", (r) => r.url().endsWith("/api/heard") && heard.push(r.url()));
    await page.goto(game.url);
    await page.getByRole("button", { name: "Say your clue" }).click();
    await say(page, "ocean", false);
    await expect(page.getByText("Hearing: ocean")).toBeVisible();
    await say(page, "ocean waves at night", true);
    await expect(page.getByLabel("Your clue")).toHaveValue("ocean waves at night");
    // Nothing was sent: not as a thought, not as a clue.
    await expect(page.getByLabel("Your clue")).toBeVisible();
    expect(heard).toEqual([]);
    await page.getByLabel("Your clue").fill("a lazy afternoon"); // edited, then given
    await page.getByRole("button", { name: "Give clue" }).click();
    await expect(page.locator("section.reveal").first()).toBeVisible();
  });

  test("a human guesser thinks aloud: the lines show, nothing moves the needle, Lock in is the move", async ({ page, game }) => {
    await page.goto(game.url);
    await page.getByLabel("Your clue").fill("a lazy afternoon");
    await page.getByRole("button", { name: "Give clue" }).click();
    await expect(page.getByRole("slider")).toBeVisible(); // round 2: you guess
    await page.getByRole("button", { name: "Think aloud" }).click();
    await say(page, "this feels", false);
    const thoughts = page.getByLabel("What you said");
    await expect(thoughts).toContainText("this feels");
    await say(page, "this feels like a quiet sunday", true);
    await expect(thoughts.locator("li")).toHaveCount(1);
    await expect(thoughts.locator("li").first()).toContainText("quiet sunday");
    await expect(page.getByRole("slider")).toHaveValue("50"); // words do not move it
    await page.getByRole("button", { name: /Lock in 50/ }).click();
    await expect(page.locator("section.reveal").last()).toContainText("guess 50");
    await expect(thoughts).toHaveCount(0); // gone with the turn
  });

  test("a line the server refuses shows its reason and moves nothing", async ({ page, game }) => {
    await page.route("**/api/heard", (route) =>
      route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ error: "it is not time to think aloud" }) }),
    );
    await page.goto(game.url);
    await page.getByLabel("Your clue").fill("a lazy afternoon");
    await page.getByRole("button", { name: "Give clue" }).click();
    await expect(page.getByRole("slider")).toBeVisible();
    await page.getByRole("button", { name: "Think aloud" }).click();
    await say(page, "hello there", true);
    await expect(page.getByRole("alert").filter({ hasText: "not time to think aloud" })).toBeVisible();
    await expect(page.getByRole("slider")).toHaveValue("50");
  });

  test("the psychic has no microphone in the guess phase", async ({ page, slowLobby }) => {
    await page.goto(slowLobby.url);
    await page.getByLabel("Seat 1", { exact: true }).selectOption("human");
    await page.getByLabel("Seat 2", { exact: true }).selectOption("llm");
    await page.getByLabel("Rounds").selectOption("3");
    await page.getByRole("button", { name: "Start" }).click();
    await page.getByLabel("Your clue").fill("a lazy afternoon");
    await page.getByRole("button", { name: "Give clue" }).click();
    await expect(page.getByText("You are the psychic: stay quiet until the reveal.")).toBeVisible();
    await expect(page.getByRole("button", { name: /Think aloud|Say your clue|Stop listening/ })).toHaveCount(0);
  });
});

test("without a recogniser there is no microphone and the page says to type", async ({ page, game }) => {
  await page.addInitScript(() => {
    delete (window as never as Record<string, unknown>).webkitSpeechRecognition;
    delete (window as never as Record<string, unknown>).SpeechRecognition;
  });
  await page.goto(game.url);
  await expect(page.getByRole("button", { name: "Say your clue" })).toHaveCount(0);
  await expect(page.getByText(/Speaking needs Chrome, Edge or Safari/)).toBeVisible();
  await page.getByLabel("Your clue").fill("a lazy afternoon");
  await page.getByRole("button", { name: "Give clue" }).click();
  await expect(page.locator("section.reveal").first()).toBeVisible();
});
