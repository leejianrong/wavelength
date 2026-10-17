# ADR-0008: The page is Svelte + Vite (TypeScript) with Material 3 tokens

- Status: Accepted (Jian, 2026-10-17: replace the hand-rolled DOM code with Svelte + Vite, TypeScript, using the frontend-design and material-design-3 skills). Supersedes [ADR-0006](0006-web-ui-with-an-embedded-vikaki-avatar-page.md) §2 only; the rest of ADR-0006 stands.
- Date: 2026-10-17
- Deciders: Jian

## Context

ADR-0006 chose strict TypeScript compiled by esbuild with no framework. The page grew to hand-written DOM builders that redraw everything on every event and save and restore focus by id. V10 adds an embedded avatar frame, subtitles and speaker marks, which would mean more of that.

## Decision

- **Svelte 5 (runes) and Vite**, TypeScript strict, checked by `svelte-check` (`make web-check`, part of `make all`). Output is unchanged for the server: `static/app.js`, `static/app.css` and the fonts in `static/assets/`, all gitignored; `static/index.html` stays a tracked plain file.
- **The page still holds no game logic.** `store.svelte.ts` keeps what the server last said and what the person has typed and not yet sent; components draw it. `dial.ts` (pure geometry) is unchanged and still unit-tested with `node --test`.
- **Material 3 as tokens, no component library.** `scripts/tokens.mjs` generates `src/theme/tokens.css` (colour roles light and dark, type, shape, motion, state layers) from one seed colour (a tuning-dial teal, `#0B7285`) with `@material/material-color-utilities`; the output is committed, `npm run tokens` regenerates it. Components (filled, tonal and text buttons, filter chips, outlined fields, filled cards) are plain CSS over the roles in `theme/base.css`, with state layers. Fonts are self-hosted (Bricolage Grotesque for headings and the dial's words, Figtree for text) so the page works offline.
- TypeScript is pinned to 6.x because `svelte-check` does not support 7 yet.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Keep esbuild and hand-rolled DOM | Redraw-everything and focus bookkeeping get worse with an iframe, subtitles and a speaker mark |
| `m3-svelte` or `@material/web` | A dependency for a handful of components; the token layer is the part that matters and is generated here |
| SvelteKit | A router and server we do not need; the Python server serves static files |

## Consequences

- More packages in `web/` (Svelte, Vite, svelte-check, the colour utilities, two fonts); still Node for the build only.
- The Playwright suite is the parity check: labels, ids and classes it relies on are kept.
- Regenerate tokens when the seed changes; never edit `tokens.css` by hand.
