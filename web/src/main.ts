import { mount } from "svelte";
import "./theme/tokens.css";
import "./theme/base.css";
import "@fontsource-variable/bricolage-grotesque/wght.css";
import "@fontsource-variable/figtree/wght.css";
import { connect } from "./api.ts";
import App from "./App.svelte";
import { app, applyDraft, applyLobby, applyProblem, applyReaction, applyState, applyThinking, applyVoice } from "./store.svelte.ts";

const root = document.getElementById("app");
if (!root) throw new Error("no #app element");
root.replaceChildren();
mount(App, { target: root });

connect({
  onLobby: applyLobby,
  onState: applyState,
  onTalk(next) {
    app.talk = next.messages;
  },
  onVoice: applyVoice,
  onDraft: applyDraft,
  onThinking: applyThinking,
  onReaction: applyReaction,
  onProblem: applyProblem,
  onConnection(next) {
    app.connection = next;
  },
});
