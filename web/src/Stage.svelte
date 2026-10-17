<script lang="ts">
  // The two avatars (vikaki's avatar page in an iframe, docs/embed.md) with the dial in the clear
  // band between them. The page draws no face and plays no sound. Sound starts locked in a browser:
  // the frame says so with `audio_locked`, and we answer `unlock` from the person's own click.
  import DialView from "./DialView.svelte";
  import { app } from "./store.svelte.ts";
  import type { StateMessage } from "./types.ts";

  let { view, hub }: { view: StateMessage; hub: string } = $props();

  let frame: HTMLIFrameElement | undefined = $state();
  let locked = $state(false);
  let captions = $state(true);

  const src = $derived(
    `${hub}/avatar?seats=2&embed=1&layout=duet&hud=0&parent=${encodeURIComponent(location.origin)}`,
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
    <div class="band"><DialView state={view} /></div>
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
