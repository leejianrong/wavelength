# ADR-0013: The human thinks aloud and speaks a clue, through the browser's recogniser

- Status: Accepted (Jian, 2026-10-19: Chrome's Web Speech API first, a direct POST to our server, the spoken clue as a follow-up in the same branch)
- Date: 2026-10-19
- Deciders: Jian

## Context

VIK-69 landed in vikaki (`human_utterance`, ADR-0024): a text-only message with partial and final transcripts, sent by the host page through the avatar frame and the hub to a seat's driver. The hub has no recogniser and no push-to-talk signal, so the page brings both. Our page already talks to our own server (`/api/draft`), so the hub hop would add a pin bump and a second path for the same words without anyone on the hub using them.

## Decision

1. **The browser recognises.** The page uses `SpeechRecognition` (`webkitSpeechRecognition` in Chrome) with interim results, started by a push-to-talk button (a click toggles it; it also stops by itself when the turn ends). Chrome sends the audio to Google's recogniser; the page says so next to the button. No button, and a line saying why, where the browser has no recogniser (Firefox). Typing keeps working everywhere. We will judge how well it hears us and decide later whether to run our own Whisper; nothing here depends on the recogniser's brand, only on the `speech.ts` seam.
2. **Direct, not through the hub.** Transcripts go to our server as `POST /api/heard {text, final}`. Nothing is sent to the hub, and the hub is never told what a person said (the hub test scans for it). The vikaki pin stays as it is.
3. **Thinking aloud is for the human guesser, during their own guess turn.** `WebSession.heard` accepts text only from the human seat, only while it is awaited for a guess, 1 to 300 characters; anything else is refused with a reason (`409`), and partials sent faster than 100 ms apart are dropped quietly, like drafts. An accepted line is sent to the page as a `heard` event (`{seat, round, text, final}`, replayed to a new page), so the page shows what the server took and the rules are enforced once. Words are only ever shown: they never become a move.
4. **A human psychic is silent in the guess phase.** The page closes its microphone and offers no button then; the server refuses the POST all the same (a human psychic's words must never reach an AI guesser, in a prompt, a frame or the hub). A human psychic is *not* asked to be silent at other times.
5. **A spoken clue stays in the browser.** For a human psychic whose clue is awaited, the same button fills the clue box with the final transcript, to be read, edited and sent with Give clue. It is not POSTed to `/api/heard`, never auto-submitted, and goes through the normal clue rules like typed text.
6. **After the reveal, what the human guesser said may reach the AI psychic.** The server keeps the guesser's final lines for the round (at most 20, 300 characters each) and adds them to the AI psychic's one reaction call, which is made after the reveal. They are cleared at the next guess turn. No call to an AI seat before the reveal contains them. They go to the model provider like any prompt, which the README says.
7. **Not spoken back.** The avatar does not repeat the human's words, and the hub is not told.

## Alternatives considered

| Option | Why not |
| --- | --- |
| Relay transcripts through the hub as `human_utterance` | Adds a pin bump and a second path; the hub keeps no use for the words. It stays available if vikaki ever reacts to speech |
| Run Whisper locally now | Heavy download and slow on a laptop; the browser's recogniser lets us judge the feature first |
| Submit a spoken clue or guess automatically | A mishearing would become a move; the person must confirm |
| Let any seat POST transcripts | A human psychic could speak the target to an AI guesser through this route |
| Send partial transcripts to the AI psychic live | The psychic would learn the guesser's mind during the guess; only after the reveal |

## Consequences

- A new leak surface, `/api/heard` and the `heard` event: cases in `tests/integration/test_web_session.py`-style tests, `tests/e2e/test_web.py`-style frame scans, the hub scan in `test_voice.py` and `web/e2e/`, including a fake recogniser in Playwright.
- `docs/web-protocol.md` gets the route and the event; `docs/voice.md` gets how to use the microphone (Chrome, HTTPS or localhost, the permission prompt, WSL).
- A reaction prompt now has an optional list of what the human said.
- Quality of recognition is unmeasured. Chrome sends audio to Google; that is stated, not hidden.
