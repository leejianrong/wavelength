<script lang="ts">
  // The two avatars (vikaki's avatar page in an iframe, docs/embed.md) with the dial in the clear
  // band between them. The page draws no face and plays no sound. Sound starts locked in a browser:
  // the frame says so with `audio_locked`, and we answer `unlock` from the person's own click.
  import { onDestroy, untrack } from "svelte";
  import DialView from "./DialView.svelte";
  import RevealDial from "./RevealDial.svelte";
  import { app, seen } from "./store.svelte.ts";
  import type { Reveal, StateMessage } from "./types.ts";

  let { view, hub }: { view: StateMessage; hub: string } = $props();

  let frame: HTMLIFrameElement | undefined = $state();
  let locked = $state(false);
  let captions = $state(true);

  // A round that finishes while you watch is shown on the stage dial for a few seconds (the needle
  // sweeps, the target and the points land), so the result is where the eyes already are.
  let result = $state<Reveal | null>(null);
  let shownRound = -1;
  let shownAt = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  // It stays up for 6 s, or 2.2 s once the person has a move to make: their dial must not stay hidden.
  $effect(() => {
    const history = view.observation.history;
    const last = history[history.length - 1];
    const myTurn = view.awaiting !== null;
    untrack(() => {
      if (last && last.round > seen.round && last.round !== shownRound) {
        shownRound = last.round;
        shownAt = Date.now();
        result = last;
      }
      if (!result) return;
      clearTimeout(timer);
      const stay = myTurn ? 2200 : 6000;
      timer = setTimeout(() => (result = null), Math.max(0, shownAt + stay - Date.now()));
    });
  });
  onDestroy(() => clearTimeout(timer));

  // `seat-1:ada,seat-2:ben` names each avatar; `2` leaves them to the hub's own order.
  const seats = $derived.by(() => {
    const personas = app.voice.seats;
    return personas && personas.every((p) => p !== null)
      ? personas.map((p, i) => `seat-${i + 1}:${p}`).join(",")
      : "2";
  });
  const src = $derived(
    `${hub}/avatar?seats=${encodeURIComponent(seats)}&embed=1&layout=duet&hud=0&parent=${encodeURIComponent(location.origin)}`,
  );
  const line = $derived(app.voice.line);
  const speaker = $derived(line ? (view.names[line.seat] ?? line.seat) : "");

  function post(message: { type: "unlock" | "audio_status" }) {
    frame?.contentWindow?.postMessage(message, hub); // the hub's origin, never "*"
  }

  $effect(() => {
    const onMessage = (e: MessageEvent) => {
      if (e.origin !== hub || e.source !== frame?.contentWindow) return;
      const type = (e.data as { type?: unknown } | null)?.type;
      if (type === "audio_locked") locked = true;
      if (type === "audio_unlocked") locked = false;
    };
    // Any click or key on this page may be the gesture the browser wants; the frame decides.
    const onGesture = () => {
      if (locked) post({ type: "unlock" });
    };
    addEventListener("message", onMessage);
    addEventListener("pointerdown", onGesture, true);
    addEventListener("keydown", onGesture, true);
    return () => {
      removeEventListener("message", onMessage);
      removeEventListener("pointerdown", onGesture, true);
      removeEventListener("keydown", onGesture, true);
    };
  });
</script>

<section class="stage" aria-label="The players">
  <div class="frame">
    <iframe
      bind:this={frame}
      title="The two players' avatars"
      {src}
      allow="autoplay"
      onload={() => post({ type: "audio_status" })}
    ></iframe>
    <div class="band">
      {#if result}
        {#key result.round}
          <RevealDial reveal={result} {view} staged showPoints />
        {/key}
      {:else}
        <DialView state={view} />
      {/if}
    </div>
  </div>
  {#if locked}
    <button type="button" class="btn btn-tonal sound" onclick={() => post({ type: "unlock" })}>Turn on sound</button>
  {/if}
  <div class="captions" role="group" aria-label="Subtitles">
    <p class="line" class:empty={!line || !captions}>
      {#if line && captions}<strong>{speaker}:</strong>{" "}{line.text}{:else}&nbsp;{/if}
    </p>
    <button type="button" class="btn btn-text" aria-pressed={captions} onclick={() => (captions = !captions)}>
      Subtitles {captions ? "on" : "off"}
    </button>
  </div>
</section>

<style>
  .stage { display: grid; gap: 8px; container-type: inline-size; }
  .frame { position: relative; height: calc(50cqw + 32px + 240px); }
  iframe { position: absolute; inset: 0; width: 100%; height: 100%; border: 0; background: transparent; }
  /* The clear band the avatar page leaves: 440 px in the middle on a wide canvas, the full width
     along the bottom on a narrow one (its own breakpoint is 772 px). */
  .band { position: absolute; left: 0; right: 0; bottom: 0; height: calc(50cqw + 32px); display: grid; place-items: center; padding: 0 16px; pointer-events: none; }
  .band > :global(svg) { width: 100%; max-width: 440px; pointer-events: auto; }
  @container (min-width: 772px) {
    .frame { height: 440px; }
    .band { left: 50%; right: auto; width: 440px; top: 0; height: auto; transform: translateX(-50%); }
  }
  .sound { justify-self: center; }
  .captions { display: flex; align-items: baseline; justify-content: space-between; gap: 8px 16px; flex-wrap: wrap; }
  .line { flex: 1 1 240px; min-height: 1.5em; color: var(--md-sys-color-on-surface); }
  .line.empty { color: transparent; }
</style>
