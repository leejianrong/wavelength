import { expect, test } from "./fixtures.ts";

const CLUE = "a lazy afternoon";

test("the avatar stage is framed from the hub with the documented URL, and the dial sits in its band", async ({
  page,
  voiceGame,
}) => {
  await page.goto(voiceGame.url);
  const frame = page.locator("section.stage iframe");
  await expect(frame).toBeVisible();
  const src = new URL((await frame.getAttribute("src")) ?? "");
  expect(src.origin).toBe(voiceGame.hub);
  expect(src.pathname).toBe("/avatar");
  expect(Object.fromEntries(src.searchParams)).toEqual({
    seats: "2",
    embed: "1",
    layout: "duet",
    hud: "0",
    parent: new URL(voiceGame.url).origin,
  });
  await expect(frame).toHaveAttribute("allow", "autoplay");
  // No token or secret in a URL a page script can read.
  expect(src.href).not.toMatch(/token/i);
  // The dial is drawn by us, over the band, and the cards no longer repeat it.
  await expect(page.locator("section.stage .band svg.dial")).toBeVisible();
  await expect(page.locator("section.round svg.dial")).toHaveCount(0);
});

test("a locked browser shows 'Turn on sound', and the person's click sends unlock to the hub's page", async ({
  page,
  voiceGame,
}) => {
  await page.goto(voiceGame.url);
  const button = page.getByRole("button", { name: "Turn on sound" });
  await expect(button).toBeVisible(); // the frame said audio_locked
  await button.click();
  await expect(button).toBeHidden(); // the frame answered audio_unlocked, which only follows unlock
  await expect(page.frameLocator("section.stage iframe").locator("#s")).toHaveText("unlocked");
});

test("a message from anywhere but the hub's frame cannot lock or unlock the page", async ({ page, voiceGame }) => {
  await page.goto(voiceGame.url);
  const button = page.getByRole("button", { name: "Turn on sound" });
  await expect(button).toBeVisible();
  // A page script posting to itself has the wrong origin and source, so it is ignored.
  await page.evaluate(() => window.postMessage({ type: "audio_unlocked" }, "*"));
  await page.waitForTimeout(300);
  await expect(button).toBeVisible();
});

test("the clue is shown as a subtitle while it is spoken, and can be switched off", async ({ page, voiceGame }) => {
  await page.goto(voiceGame.url);
  await page.getByLabel("Your clue").fill(CLUE);
  await page.getByRole("button", { name: "Give clue" }).click();
  const captions = page.getByRole("group", { name: "Subtitles" });
  await expect(captions).toContainText(`You: ${CLUE}`);
  await page.getByRole("button", { name: /Subtitles on/ }).click();
  await expect(captions).not.toContainText(CLUE);
  await expect(page.getByRole("button", { name: /Subtitles off/ })).toHaveAttribute("aria-pressed", "false");
});

test("the match is played to the end with voice on, and the recap replaces the stage", async ({ page, voiceGame }) => {
  await page.goto(voiceGame.url);
  await page.getByLabel("Your clue").fill(CLUE);
  await page.getByRole("button", { name: "Give clue" }).click();
  await expect(page.getByText("The clue:")).toBeVisible();
  // The guess dial is the one in the band, and it is still keyboard-operable through the slider.
  await expect(page.locator("section.stage .band svg.dial.interactive")).toBeVisible();
  await page.getByRole("button", { name: /Lock in/ }).click();
  await expect(page.locator("section.recap")).toBeVisible();
  await expect(page.locator("section.stage")).toHaveCount(0);
});

test("with no hub the game is a text game: no avatars, the dial in its card, and it plays on", async ({
  page,
  deadHubGame,
}) => {
  await page.goto(deadHubGame.url);
  await expect(page.getByLabel("Your clue")).toBeVisible();
  await expect(page.locator("section.stage")).toHaveCount(0);
  await expect(page.locator("section.round svg.dial")).toBeVisible();
  await page.getByLabel("Your clue").fill(CLUE);
  await page.getByRole("button", { name: "Give clue" }).click();
  await expect(page.getByText("The clue:")).toBeVisible();
});

test.describe("on a phone", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("the stage fits the screen, with the dial in the band below the avatars", async ({ page, voiceGame }) => {
    await page.goto(voiceGame.url);
    const frame = page.locator("section.stage iframe");
    await expect(frame).toBeVisible();
    const scrolls = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    expect(scrolls).toBe(false);
    const band = await page.locator("section.stage .frame > .band").boundingBox();
    const box = await frame.boundingBox();
    expect(band && box).toBeTruthy();
    // On a narrow frame the band is the full width along the bottom (vikaki's duet layout).
    expect(Math.round(band!.width)).toBe(Math.round(box!.width));
    expect(Math.round(band!.y + band!.height)).toBe(Math.round(box!.y + box!.height));
  });
});
