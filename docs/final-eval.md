# Final eval: notes against needle steps (AGE-41)

Run on 2026-10-25. Model `deepseek/deepseek-v4.1-flash` in both seats, seed 1, 30 rounds per arm, same deck and targets.

## Result

| arm | rounds | points per round | bullseyes | model calls |
| --- | --- | --- | --- | --- |
| notes (`--think`) | 30 | 1.93 | 7 | 120 |
| notes and needle steps (`--think --needle-steps`) | 30 | 1.83 | 7 | 145 |
| uniform-random guesser | | 0.57 | | |

The arms are not distinguishable. A rough standard error for 30 rounds is about 0.17 per arm, so the 0.10 gap is noise. Needle steps neither helped nor hurt on this sample. The earlier no-notes (1.67, 60 rounds) and notes (2.08, 53 rounds) figures in ADR-0010 sit within about two standard errors of these.

Decision: leave needle steps on in the web UI (they are what makes the dial watchable) and off in `wavelength.eval`. They are not shown to play better, and V15 does not claim it.

## What happened

- Both arms completed all 30 rounds. Neither hit the OpenRouter 403 that stopped the earlier notes run at round 53, so AGE-42 (its cause) is still open. A workspace guardrail that blocks a model answers 404 (see below), and is the leading, unproven, guess.
- Two needle steps failed in the steps arm: one `ReadTimeout`, one semula 422 `invalid_answer` ("needs content or tool_calls"), because the model returned reasoning and no content. The game fell back to the last needle each time.
- The report's call breakdown shows "guess 1" for the steps arm, because steps are not decide calls. Known; not fixed here.

## How it was run

Through semula 0.3.0 record-through (project `notes` and `steps`, `upstream_max_calls` 300 each), so both arms are recorded in a volume and replay free. Semula counted 120 and 144 upstream calls (181k and 174k prompt tokens, 169k and 106k completion tokens).

The first attempt used the Makefile's old default, `deepseek/deepseek-v4-flash` (no `.1`). A guardrail in the OpenRouter workspace blocks it and answers `404 ... Model blocked by guardrail` before any call is made or charged. The default is now `deepseek/deepseek-v4.1-flash`.

## Cost

About 35 cents (the key's usage went from $3.646 to $3.993). Jian approved up to 25 cents on an estimate of 5 to 15 cents. The estimate was low because the model spends many reasoning tokens (about 274k completion tokens over both arms), which the earlier "cents" figures hid. The overrun was found after the runs, not during: the call caps bound calls, not tokens. For a future run, set `upstream_max_tokens` as well.

## Limits

One seed, 30 rounds each, one model playing both seats. Not a measurement of any other model.
