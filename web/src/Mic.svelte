<script lang="ts">
  // The push-to-talk button (ADR-0013). `think`: a human guesser thinks aloud, the lines go to the server
  // to be shown (never a move). `clue`: a human psychic says a clue; the final text fills the clue box to
  // edit and send, and never leaves the browser. A human psychic has no button in the guess phase.
  import { onDestroy } from "svelte";
  import { postHeard } from "./api.ts";
  import { clampText } from "./dial.ts";
  import { createRecogniser, errorReason, recogniserAvailable, type Recogniser } from "./speech.ts";
  import { draft } from "./store.svelte.ts";

  let { mode, maxChars = 80 }: { mode: "think" | "clue"; maxChars?: number } = $props();

  const available = recogniserAvailable();
  let listening = $state(false);
  let preview = $state("");
  let problem = $state("");
  let wanted = false;
  let recogniser: Recogniser | null = null;

  async function onText(text: string, final: boolean) {
    if (mode === "clue") {
      if (final) {
        draft.clue = clampText(text, maxChars);
        preview = "";
      } else preview = text;
      return;
    }
    const refused = await postHeard(text, final);
    if (refused) problem = refused;
  }

  function start() {
    problem = "";
    recogniser ??= createRecogniser({
      onText,
      onStop(reason) {
        const why = errorReason(reason);
        if (why) {
          problem = why;
          wanted = false;
        }
        // The browser ends a session after a pause; keep listening while the person wants it.
        if (wanted) recogniser?.start();
        else listening = false;
      },
    });
    wanted = true;
    listening = true;
    recogniser?.start();
  }

  function stop() {
    wanted = false;
    listening = false;
    preview = "";
    recogniser?.stop();
  }

  onDestroy(stop); // the turn ended: the form is gone, and so is the microphone
</script>

{#if available}
  <div class="mic">
    <button
      type="button"
      class="btn btn-tonal"
      aria-pressed={listening}
      onclick={() => (listening ? stop() : start())}
    >
      {listening ? "Stop listening" : mode === "clue" ? "Say your clue" : "Think aloud"}
    </button>
    {#if listening && preview}<span class="hint" aria-live="polite">Hearing: {preview}</span>{/if}
    {#if problem}<span class="problem-text" role="alert">{problem}</span>{/if}
    <span class="hint">Chrome sends what you say to Google to turn it into text.</span>
  </div>
{:else}
  <p class="hint">Speaking needs Chrome, Edge or Safari. You can type instead.</p>
{/if}

<style>
  .mic { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; }
  .problem-text { color: var(--md-sys-color-error); }
</style>
