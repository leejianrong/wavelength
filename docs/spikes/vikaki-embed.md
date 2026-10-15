# Spike V6: vikaki's avatar page in another page's iframe

Date 2026-10-16. Code: `spikes/vikaki-embed/`. vikaki at `5716318` (`main`, PR #66), a clean clone, not the working tree. Decision it feeds: [ADR-0006](../adr/0006-web-ui-with-an-embedded-vikaki-avatar-page.md).

## Verdict

**The embed works.** A page on another port (`:8890`) frames `http://127.0.0.1:8787/avatar?seats=2`; the avatars load, connect to the hub, and speak; a Python driver using `vikaki-client` drives both seats and gets `speech_started` and `speech_finished` back from the page. **One thing is not yet proven:** the browser's audio-autoplay gate. Automated browsers do not enforce it, so it needs a real browser (below). ADR-0006 stays Proposed until that is checked.

## What was tested

| Question | Result |
| --- | --- |
| Does the page allow framing? | Yes. The avatar page sends no `X-Frame-Options` or CSP; the iframe loaded in Chromium from another port. |
| Does the avatar connect and speak inside the frame? | Yes, in all five variants (click on the parent, click inside the frame, `allow="autoplay"` present or absent, no click). The page reported `ready`, and speech ended with `speech_finished` from the page's own clock. |
| Does it look right? | Two avatars fill the frame with name chips and a caption strip (`embed.png`). `?bg=<hex>` and `?hud=0` already work. There is no free area for a game panel: that is the duet layout, VIK-68. |
| Two seats from one Python script? | Yes. A whole-table driver spoke `seat-1` then `seat-2`, each waited on with `wait_finished`. |
| Cancel? | During playback: `speech_interrupted` in about 6 ms (fake voice) and 0 ms (Kokoro). **Before the first audio exists with Kokoro: no event in 15 s, 4 of 4 tries.** Later lines were still spoken. Filed as VIK-71. |
| Latency to first audio, real voice (Kokoro, CPU) | 1.6 to 1.9 s with no page open (the hub keeps the clock). 3.0 to 3.7 s with the embedded page open, rendered in headless Chromium with software WebGL on the same CPU; this is an upper bound, not a measurement of a real GPU browser. |
| Can a game page open the hub socket itself? | No: the hub refuses WebSockets from other browser origins (`origin not allowed`) unless `allowedOrigins` is set, and the CLI has no flag for it. This does not matter for the design: the embedded page is served by the hub, and the Python game server sends no `Origin`. The browser never talks to the hub. |

## Not proven: audio unlock

Headless Chromium (Playwright's headless shell and `channel: "chromium"`, even with `--autoplay-policy=document-user-activation-required`) reports the page's `AudioContext` as `running` with no click at all, so the gate was not exercised. Check it by hand in a real browser, on the machine you will play on (Windows Chrome with the hub in WSL is the case that matters):

1. Start the hub and `serve.ts` (see the spike README), open `http://127.0.0.1:8890/?allow=autoplay`.
2. Without clicking anything in the page, wait for the avatars, then press **2. Say a line**. Do you hear it? (This is the "no click" case.)
3. Reload. Press **1. Enable sound**, then **2. Say a line**. Do you hear it?
4. Reload, click once on the avatars (inside the frame), then **2**. Do you hear it?
5. Repeat 2 to 4 with `?allow=none`.

The result decides how much VIK-66 (the unlock handshake) matters. If the sound plays after any click on the page, the host page can simply put a "Start" button before the match and the handshake is a nice-to-have.

## Consequences for the plan

- V7 to V10 can proceed on the iframe approach. No vikaki change blocks the start of V7.
- VIK-64 (embed mode) and VIK-68 (duet) are cosmetic and wanted; VIK-65 shrinks to documentation; VIK-67 (events to the parent) is optional because the Python server hears the same events as the driver and can push them to the browser.
- Plan for ~2 s of voice latency (1.6 s synthesis) plus load, and overlap the guesser's call with the clue's speech (ADR-0006 §6). Re-measure on a GPU browser.
- A cancel before first audio should not be relied on until VIK-71.
- Pacing note: the driver learns `speech_started` and `speech_finished` from the open page, so the match naturally waits for a page that is really playing. With no page open the hub keeps time itself, so a driver never stalls.
