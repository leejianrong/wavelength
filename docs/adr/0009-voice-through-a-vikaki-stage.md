# ADR-0009: Voice and faces: a speaker-only tap and an avatar stage that holds the dial

- Status: Accepted (Jian, 2026-10-17: go ahead once vikaki's VIK-64 to 71 landed). Fills in [ADR-0006](0006-web-ui-with-an-embedded-vikaki-avatar-page.md) §3, §4, §5 and §6.
- Date: 2026-10-17
- Deciders: Jian

## Context

vikaki now has the embed work this needed (pinned at `1318f80`, its `docs/embed.md`): an avatars-only page, a duet layout with a clear central band, an `audio_locked` / `unlock` handshake, speech events, an immediate answer to a cancel, and an explicit list of origins that may frame the page. ADR-0006 already chose an iframe and a `VoiceTap`; this records how they are built, since the choices are costly to undo.

## Decision

1. **`VoiceTap` (`voice.py`) speaks; it does not read the game.** Its methods take a seat and a line of text that is already public (a clue, an AI guesser's banter, a chat reply), or a round's public points for the faces. It is never given an observation, so there is nothing to filter and nothing to forget to filter. `WebSession` is the one place that decides what is public, by the same rules as the talk log: banter only from a guess turn, no chat refusal, nothing from a chat with a psychic. The clue is spoken in a neutral voice (a feeling could hint at the target's distance).
2. **One driver per seat** (vikaki ADR-0017), each bound to a hub seat (`seat-1`, `seat-2`, in order). The tap hears only about its own lines.
3. **Pacing:** a clue is sent and the guesser starts thinking at once, while it is spoken. At the guess the session waits for the clue to finish, speaks the banter and waits for that, and only then shows the reveal. Every wait has a timeout (20 s); a line that does not finish is cancelled and play goes on.
4. **The voice is optional and never fatal.** No hub, no `voice` extra, a dropped connection or a busy seat: the tap switches off, tells the page once (`voice` event, status `off`), and the game is the text game. vikaki is an optional dependency (`pip install wavelength[voice]`), pinned to a commit like the framework.
5. **The browser never talks to the hub's socket.** The page frames the hub's avatar page (`/avatar?seats=2&embed=1&layout=duet&hud=0&parent=<this origin>`, `allow="autoplay"`); the server tells it where the hub is (`voice_hub` in `state`, an origin, never the token). The token, if any, is for the Python drivers only.
6. **A stage holds the dial.** With voice on, the avatars and the dial are one piece (`Stage.svelte`): the dial is drawn by us in the band vikaki leaves clear (440 px in the middle on a wide frame, the full width below the avatars on a phone). Without voice the dial stays in its card, as before. The stage is shown only while the voice status is `on`.
7. **Sound: the handshake, with every click as a chance.** While the frame reports `audio_locked`, any click or key on our page posts `unlock` to the hub's origin, and a visible "Turn on sound" button does the same. We accept messages only from the frame's own window and the hub's origin, and post only to that origin, never `*`. vikaki's in-frame "Click for sound" button stays reachable as the fallback.
8. **Subtitles** come from the server's `voice` event (the line being spoken, from the hub's `speech_started` and `speech_finished`), not from the iframe, so they show the same text whatever the avatar page does. A toggle hides them.

## Alternatives considered

| Option | Why not |
| --- | --- |
| Give the tap the observation and let it pick what to say | Puts the leak boundary inside a module that talks to the network. The text-only interface makes a leak a type error rather than a review finding |
| Have the page listen to the iframe's speech events for subtitles and pacing | Pacing must work with no page open, and the iframe's events go only to the framing page. The server already hears the same events as a driver |
| Keep the dial in its card under the frame (the workaround in the V6 spike) | Judged not worth building twice once duet landed |
| Start the guesser only after the clue is spoken | Adds the whole speaking time to every round for no gain; the guesser sees only public text either way |
| Make vikaki a required dependency | A game that needs a 410 MB voice to start is worse than one that can be played silently |

## Consequences

- A new leak surface: the hub traffic. `tests/integration/test_voice.py` scans everything a whole match sends to a fake hub against an allow-list of message kinds and keys, and for words that only an observation holds.
- A `voice` event and a `voice_hub` field join the web protocol (`docs/web-protocol.md`).
- `unlock` is unproven outside Chromium: vikaki tested only there. The in-frame button is the fallback, and the manual check in Windows Chrome with the hub in WSL is listed in `docs/voice.md`.
- Moving to a hub on another machine would need the hub to answer other `Host` names (it refuses them on purpose) and `--frame-ancestors` for our origin.
