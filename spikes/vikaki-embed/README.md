# Spike: vikaki's avatar page inside another page (V6)

Throwaway code. Write-up and findings: `docs/spikes/vikaki-embed.md`.

- `host.html` + `host.ts`: a stand-in game page on `:8890` that embeds `http://127.0.0.1:8787/avatar?seats=2`.
- `drive.py`: a Python driver using `vikaki-client`; speaks, waits for `speech_finished`, cancels.
- `probe.ts`: Playwright runs the host page in five click/`allow` variants and records the AudioContext state and the driver's timings.
- `serve.ts`: serves the host page for your own browser, with a "say a line" button.

Needs a vikaki checkout on `main` (kept apart from any working tree), built, with its hub running:

```bash
git clone https://github.com/leejianrong/vikaki.git /tmp/vikaki && cd /tmp/vikaki
pnpm install --frozen-lockfile && pnpm build && make install-voice          # the voice is optional (--tts fake)
pnpm serve --port 8787 --tts kokoro --personas personas.table.example.yaml  # leave running
VIKAKI_DIR=/tmp/vikaki pnpm exec tsx <this folder>/serve.ts                 # host page on :8890
VIKAKI_DIR=/tmp/vikaki pnpm exec tsx <this folder>/probe.ts                 # the automated variants
```

Needs `uv` for the Python driver. Nothing here is installed into this repo.
