# Voice and faces

`wavelength web --voice fake|real` gives each player a face and the AI a voice, through a [vikaki](https://github.com/leejianrong/vikaki) hub. Without it, or if the hub cannot be reached, the game is the same game in text and the page shows no avatars. Design: [ADR-0009](adr/0009-voice-through-a-vikaki-stage.md).

## Run it

```bash
git clone https://github.com/leejianrong/vikaki ~/vikaki && cd ~/vikaki
git checkout 1318f80                      # the commit this repo is tested against
pnpm install --frozen-lockfile && pnpm build
make install-voice                        # only for the real voice (Kokoro, about 410 MB)

cd ~/wavelength
make web-voice VIKAKI_DIR=~/vikaki        # a silent test voice: faces, speaker marks, subtitles
make web-voice VIKAKI_DIR=~/vikaki VOICE=real
```

`make web-voice` starts the hub (if something already listens on the hub's port, it uses that hub as it is and says so) (`pnpm serve` in that checkout, with `--frame-ancestors` set to this server's origin) and the game, and stops both on exit. To run a hub yourself, start `vikaki serve --port 8787 --frame-ancestors http://127.0.0.1:8765,http://localhost:8765 --personas personas.table.example.yaml` and use `wavelength web --voice fake`; `--hub` names another address.

| Flag | |
| --- | --- |
| `--voice off\|fake\|real` | `off` is the default. `fake` and `real` are the hub's `--tts` values when this server starts the hub. |
| `--hub URL` | The hub's address, default `http://127.0.0.1:8787`. A bare origin on `127.0.0.1`, `localhost` or `[::1]`: the hub refuses other `Host` names. |
| `--vikaki-dir PATH` (or `VIKAKI_DIR`) | A built vikaki checkout to start the hub from. Without it a hub must already be running. |
| `VIKAKI_TOKEN` | If the hub was started with `--token`, the drivers send it. It is never sent to a page. |

The Python side needs the `voice` extra (`make install` installs it).

## Who looks and sounds like whom

A named player can pick its avatar and voice with an optional `voice` in the players file, the name of a persona in the hub's personas file (`personas.table.example.yaml` has `ada`, `ben` and `cy`):

```toml
[[player]]
name = "Dry Sceptic"
model = "deepseek/deepseek-v4.1-flash"
voice = "ben"
personality = "..."
```

A seat with no `voice` (a human, a bot, an unnamed AI) gets the first persona no other seat has, so two avatars never look alike. A `voice` the hub does not have is logged and replaced the same way; the voice stays on. A hub started without a personas file leaves every seat to its own default.

## What you get

The two avatars face each other with the dial between them. The speaker is lit and the other avatar is dimmed; a thinking avatar shows the thinking pose. The clue is spoken by the psychic's avatar, an AI guesser's remark with its guess by theirs, and an AI chat partner's reply by theirs. After each reveal both avatars react silently to the points. The reveal waits until the clue has been said (at most 20 s). Subtitles show the line being spoken; "Subtitles" switches them off.

## Sound

A browser keeps the avatar frame silent until a person has interacted with it. The frame says so, and the page offers a **Turn on sound** button; any click or key on the page also tries to unlock it. If that does not work in your browser, click the avatars once (vikaki shows a "Click for sound" button in the frame's corner). A line spoken while locked is silent, not delayed.

## Speaking (the microphone)

A **Think aloud** button (human guesser, during your own guess) and a **Say your clue** button (human psychic, while a clue is awaited) use the browser's speech recogniser (ADR-0013). It is Chrome's Web Speech API: **Chrome sends what you say to Google to turn it into text**, it needs `localhost`/`127.0.0.1` or HTTPS and your permission for the microphone, and Firefox has none (the page says to type). Words you think aloud are shown on the page; they never move the needle or lock a guess. After the reveal, an AI psychic's reaction call sees the lines you said that round, so they reach the model provider like any prompt. A spoken clue only fills the clue box: you read it, fix it and press Give clue. A human psychic has no microphone in the guess phase. The hub is not involved. On WSL, open the page in Windows Chrome and allow the microphone for `localhost`.

## Check by hand (Windows Chrome, hub in WSL)

Done once on 2026-10-18 in Windows Chrome with the hub in WSL: sound works, fake and real voice. Firefox and Safari are untested. Automated tests cover the handshake only against a stand-in page, and headless Chromium reports sound as already allowed, so the real gate needs a real browser:

1. Start `make web-voice VIKAKI_DIR=... VOICE=real` in WSL.
2. In Windows Chrome open `http://localhost:8765` (not the WSL machine's own address, which the hub refuses).
3. Start a match, human and bot. Without touching the avatars, press **Turn on sound** if it shows, then give a clue. Do you hear it?
4. Repeat in a fresh tab but click only the page background first (any click should unlock). Repeat in Firefox and Safari if you use them.

## On WSL

Open everything as `http://localhost:<port>` or `http://127.0.0.1:<port>` in the Windows browser; WSL forwards both. If Windows cannot reach the ports, use mirrored networking (`networkingMode=mirrored` in `%UserProfile%\.wslconfig`, then `wsl --shutdown`) rather than binding `0.0.0.0`. With a list of `--frame-ancestors`, `http://localhost:8765` and `http://127.0.0.1:8765` are different origins: `--vikaki-dir` lists both.
