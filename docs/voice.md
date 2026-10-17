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

`make web-voice` starts the hub (`pnpm serve` in that checkout, with `--frame-ancestors` set to this server's origin) and the game, and stops both on exit. To run a hub yourself, start `vikaki serve --port 8787 --frame-ancestors http://127.0.0.1:8765,http://localhost:8765 --personas personas.table.example.yaml` and use `wavelength web --voice fake`; `--hub` names another address.

| Flag | |
| --- | --- |
| `--voice off\|fake\|real` | `off` is the default. `fake` and `real` are the hub's `--tts` values when this server starts the hub. |
| `--hub URL` | The hub's address, default `http://127.0.0.1:8787`. A bare origin on `127.0.0.1`, `localhost` or `[::1]`: the hub refuses other `Host` names. |
| `--vikaki-dir PATH` (or `VIKAKI_DIR`) | A built vikaki checkout to start the hub from. Without it a hub must already be running. |
| `VIKAKI_TOKEN` | If the hub was started with `--token`, the drivers send it. It is never sent to a page. |

The Python side needs the `voice` extra (`make install` installs it).

## What you get

The two avatars face each other with the dial between them. The speaker is lit and the other avatar is dimmed; a thinking avatar shows the thinking pose. The clue is spoken by the psychic's avatar, an AI guesser's remark with its guess by theirs, and an AI chat partner's reply by theirs. After each reveal both avatars react silently to the points. The reveal waits until the clue has been said (at most 20 s). Subtitles show the line being spoken; "Subtitles" switches them off.

## Sound

A browser keeps the avatar frame silent until a person has interacted with it. The frame says so, and the page offers a **Turn on sound** button; any click or key on the page also tries to unlock it. If that does not work in your browser, click the avatars once (vikaki shows a "Click for sound" button in the frame's corner). A line spoken while locked is silent, not delayed.

## Check once by hand (Windows Chrome, hub in WSL)

Automated tests cover the handshake only against a stand-in page, and headless Chromium reports sound as already allowed, so the real gate needs a real browser:

1. Start `make web-voice VIKAKI_DIR=... VOICE=real` in WSL.
2. In Windows Chrome open `http://localhost:8765` (not the WSL machine's own address, which the hub refuses).
3. Start a match, human and bot. Without touching the avatars, press **Turn on sound** if it shows, then give a clue. Do you hear it?
4. Repeat in a fresh tab but click only the page background first (any click should unlock). Repeat in Firefox and Safari if you use them.

## On WSL

Open everything as `http://localhost:<port>` or `http://127.0.0.1:<port>` in the Windows browser; WSL forwards both. If Windows cannot reach the ports, use mirrored networking (`networkingMode=mirrored` in `%UserProfile%\.wslconfig`, then `wsl --shutdown`) rather than binding `0.0.0.0`. With a list of `--frame-ancestors`, `http://localhost:8765` and `http://127.0.0.1:8765` are different origins: `--vikaki-dir` lists both.
