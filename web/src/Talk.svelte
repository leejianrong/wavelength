<script lang="ts">
  // The conversation: guess-turn banter from the AIs, and chat between a human and an AI partner.
  import { sendChat } from "./api.ts";
  import { app, draft } from "./store.svelte.ts";
  import type { StateMessage } from "./types.ts";

  let { state }: { state: StateMessage } = $props();
  const partner = $derived(state.chat_with);
  const name = (seat: string) => state.names[seat] ?? seat;

  async function submit(e: SubmitEvent) {
    e.preventDefault();
    const text = draft.chat.trim();
    if (!text || draft.chatWaiting) return;
    draft.chatWaiting = true;
    draft.chat = "";
    const refused = await sendChat(text);
    draft.chatWaiting = false;
    if (refused) app.notice = refused;
  }
</script>

{#if app.talk.length > 0 || partner}
  <section class="card" aria-label="Chat">
    <h2>Chat</h2>
    <ul class="talk" aria-label="Conversation" aria-live="polite">
      {#each app.talk.slice(-12) as m}
        <li class={m.kind}><strong>{name(m.seat)}: </strong>{#if m.kind === "banter"}<em>{m.text}</em>{:else}{m.text}{/if}</li>
      {:else}
        <li class="hint">Nothing said yet.</li>
      {/each}
    </ul>
    {#if partner}
      <form class="row chat" onsubmit={submit}>
        <input
          id="chat"
          type="text"
          autocomplete="off"
          maxlength="500"
          bind:value={draft.chat}
          placeholder="Say something to {name(partner)}"
          aria-label="Say something to {name(partner)}"
        />
        <button type="submit" class="btn btn-tonal" disabled={draft.chatWaiting || draft.chat.trim() === ""}>
          {draft.chatWaiting ? "Waiting…" : "Send"}
        </button>
      </form>
    {/if}
  </section>
{/if}

<style>
  .talk { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; max-height: 14rem; overflow-y: auto; }
  .talk li { overflow-wrap: anywhere; }
  .talk li.banter { color: var(--md-sys-color-on-surface-variant); }
  .chat input { flex: 1 1 200px; width: auto; }
</style>
