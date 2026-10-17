<script lang="ts">
  import { postMove } from "./api.ts";
  import { focusOnTurn } from "./a11y.ts";
  import { countWords } from "./dial.ts";
  import { app, draft } from "./store.svelte.ts";
  import type { StateMessage } from "./types.ts";

  let { state }: { state: StateMessage } = $props();
  const maxWords = $derived(state.clue_limits?.max_words ?? null);
  const words = $derived(countWords(draft.clue));

  async function submit(e: SubmitEvent) {
    e.preventDefault();
    if (draft.submitting || draft.clue.trim() === "") return;
    draft.submitting = true;
    const problem = await postMove({ type: "clue", text: draft.clue });
    if (problem) {
      draft.submitting = false;
      app.notice = problem;
    }
  }
</script>

<form class="row" onsubmit={submit}>
  <div class="field grow">
    <label for="clue">Your clue</label>
    <input
      id="clue"
      type="text"
      autocomplete="off"
      maxlength={state.clue_limits?.max_chars ?? 80}
      bind:value={draft.clue}
      {@attach focusOnTurn}
      aria-describedby="clue-help"
    />
  </div>
  <button type="submit" class="btn btn-filled" disabled={draft.submitting || draft.clue.trim() === ""}>Give clue</button>
  <span id="clue-help" class="hint">{maxWords ? `${words} / ${maxWords} words` : `${words} words`}</span>
</form>

<style>
  .grow { flex: 1 0 100%; }
  form { align-items: end; }
</style>
