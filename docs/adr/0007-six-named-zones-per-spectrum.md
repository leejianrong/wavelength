# ADR-0007: Each spectrum has six hand-written zone names; clues may not use them

- Status: Accepted (Jian, 2026-10-16: "hand-written words per pair", and a much bigger deck)
- Date: 2026-10-16
- Deciders: Jian

## Context

The target and the guess are shown as numbers (9, 78) on a 0-100 dial. Nobody has a feel for "78 between Quiet and Loud", so a human psychic cannot easily think of a clue and an LLM is given a bare number too. Players want "Deafening" or "Slightly soft".

Most spectra are single words, but many are nouns ("Gift", "Chore") or phrases ("Worth waiting for"), so a template like "Very <endpoint>" reads badly. Wording needs to be written per pair.

## Decision

- **Six zones per spectrum**, equal in width: value `v` is in zone `min(5, v * 6 // 100)`, so 0-16, 17-33, 34-49, 50-66, 67-83, 84-100. The first is the left extreme, the last the right extreme. Both Python (`deck.region_index`) and the page (`web/src/regions.ts`) implement this and are tested against one golden table of all 101 values.
- **Deck format 2** adds `regions`: exactly six distinct, non-empty labels per spectrum, ordered left to right, at most 28 characters. Format 1 decks still load; their zones are generated as "Far toward X", "Toward X", "A little toward X" and the mirror. A `Spectrum` therefore always carries six labels, so nothing downstream needs a fallback.
- **The zones are public.** They are sent in the observation's `spectrum` to both seats, so the guesser sees the vocabulary. They say nothing about which zone holds the target.
- **Clues may not contain a zone name** (as a whole word, or the whole phrase for a multi-word zone), exactly as they may not contain the spectrum's endpoint words. Otherwise a psychic could say "Deafening" and the guesser, who sees all six names, would know the zone. The rejection names the zone, so a model can fix it.
- **Numbers stay as secondary information.** The psychic sees its target as "Deafening (84)", the reveal and recap show zone and number, and a guesser sees the zone of their current guess while dragging. An LLM psychic is told its target's zone as well as the number.
- **A much bigger deck**, written by hand (original wording, not another game's cards): several hundred pairs, each with six zone names, validated on load and by tests.

## Alternatives considered

| Option | Why not |
|--------|---------|
| A template for every pair ("Far toward Gift") | Works with no authoring, but flat and not what was asked for |
| "Very X / X / Slightly X" | Good for adjective pairs, wrong for nouns and phrases |
| Eight zones | Finer, but more words to write and to tell apart; six already gives three levels per side |
| Show zones only to the psychic | The guesser would still face a bare number, and the reveal would be the first time zone words appear |
| Allow zone names in clues | Gives the zone away to a guesser who sees all six names |

## Consequences

- The deck file roughly quadruples; every spectrum needs six distinct, ordered, vivid words, which the validator can check for shape but not for taste.
- Clue rules tighten (ADR-0004 gains a rule). A common word as a zone name blocks that word as a clue, so zone names should be distinctive; an LLM psychic will see more rejections, which the guard already handles.
- Saved states and observations gain `regions` inside `spectrum`; older dumps without it load with generated zones.
- Two implementations of the zone rule, guarded by one golden file.
