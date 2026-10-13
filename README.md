# wavelength

Wavelength for one human and one LLM agent, or two LLM agents, built on [`agent-game-framework`](https://github.com/leejianrong/agent-game-framework). One player (the psychic) sees a hidden target on a dial between two opposites and gives a short clue; the other (the guesser) sets the dial. It is cooperative: points are shared, the roles swap each round, and you win together by reaching the goal score.

**Status:** V1 done: the engine, the hidden target, clue validation and the ASCII dial work against a scripted bot. LLM seats (V3) and chat (V4) are next; see [`docs/SLICES.md`](docs/SLICES.md).

## Quick start

```
uv sync --all-extras --dev
make play
```

That plays one round: you write a clue for a hidden target, and a bot guesses. The same thing by hand, with more rounds:

```
uv run wavelength play wavelength --config rounds=6 --config seed=7 \
  --seat A=human --seat B=bot:wl-random
```

`--config` takes `rounds`, `target_score`, `seed` and `deck` (a JSON file shaped like `src/wavelength/data/spectra.json`). The same seed gives the same match. `--json` prints one JSON line per turn, showing only what the human seat is allowed to see; `--omniscient` shows everything.

A clue is one line of 1-6 words. It may not contain numbers, position words ("left", "middle"), or the spectrum's own words; the game rejects it with the reason and asks again.

Play, rules and design are in [`docs/PLAN.md`](docs/PLAN.md) and [`docs/adr/`](docs/adr).

This is an independent implementation with original content. "Wavelength" is a commercial game by Palm Court / CMYK; this project is not affiliated with or endorsed by them.

## License

Apache License 2.0, see `LICENSE`.
