# Trying the speech recogniser by hand (AGE-43)

ADR-0013 uses the browser's `SpeechRecognition` and says we would judge it before deciding on a local Whisper. Only a person with a microphone can judge it: the tests use a fake. This page is what to try, what to write down, and what is known so far. The verdict goes in ADR-0013 (a new "Verdict" section) once the trial is done.

## The trial (about 15 minutes, Windows Chrome)

1. `make web` (a bot opponent, no key needed). Open the printed address in Chrome on Windows. Allow the microphone when asked. If the server runs in WSL and the page cannot reach it, use the WSL address Chrome can see (`localhost` forwarding normally works).
2. **Think aloud.** Be the human guesser against the bot. In each guess turn press the push-to-talk button, say what you think about the clue, and watch the line under the dial. Do about 10 rounds.
3. **Say your clue.** Be the psychic (swap seats). Press the button, say a clue, and read what lands in the clue box before you send it. Do about 10 clues, including a few that are hard to hear: a rare word, a name, two words that sound alike, a number.
4. Write down for each attempt (a table is fine): what you said, what appeared, how long after you stopped speaking the final line arrived, and whether the interim text kept up while you spoke.

## What to look for

| Question | Good enough if | A Whisper is worth building if |
| --- | --- | --- |
| Misheard clues | fewer than about 1 in 10 need a retype | clues are often wrong, or wrong in a way that changes the game |
| Delay to the final line | under about 1.5 s after you stop | it often takes several seconds, or the button sticks |
| Interim text | follows you as you speak | it lags, or only the final line shows |
| Reliability | works every time the button is pressed | it sometimes does nothing, or stops by itself mid-sentence |
| Privacy | you are happy that audio goes to Google (the page says so) | you want it to work offline, or not to send voice anywhere |

Also note whether the permission prompt, the microphone choice (headset against laptop) or background noise changed the result.

## Other browsers

- **Firefox:** `SpeechRecognition` is not offered by default, so the page shows no button and says so. Check that the line appears and that typing works. Expected, unverified here.
- **Safari:** offers `webkitSpeechRecognition`, but it relies on the system's dictation and may ask to enable Siri or Dictation; behaviour differs from Chrome. Try the same 10 attempts if you have a Mac, and note any prompt or failure.

## What a local Whisper would cost

From general knowledge, not measured here, so confirm before relying on any figure:

| | Chrome's recogniser (now) | A local Whisper |
| --- | --- | --- |
| Where it runs | Google's servers, from the browser | our machine (whisper.cpp or faster-whisper), or in the page (WASM or WebGPU) |
| Offline | no | yes after a one-off model download |
| Size | none | tiny to small models are roughly 75 MB to 500 MB |
| Licence | the browser's | Whisper and its weights are MIT |
| Interim text | yes, built in | not built in: it works on chunks, so the live line would need our own buffering |
| Work for us | none | a server route that takes audio (a new leak surface for ADR-0013's rules), a model download, a CPU or GPU budget, and a new test double |
| Latency | network round trip | depends on the machine; a small model on a laptop CPU is usually slower than real time to start with |

The decision rule is the table above: build it only if the trial shows misheard clues or delays that spoil the game, or if offline or private speech matters to you. Otherwise record "keep Chrome's recogniser" and the reasons.

## After the trial

Send the table and your verdict. Then the ADR-0013 "Verdict" section is written from it: what was tried, what was heard wrongly, the Firefox and Safari behaviour, and the decision on Whisper.
