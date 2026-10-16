import { connect, type Connection } from "./api.ts";
import type { Context } from "./context.ts";
import type { LobbyMessage, StateMessage, TalkEntry } from "./types.ts";
import { render } from "./view.ts";

const root = document.getElementById("app");
if (!root) throw new Error("no #app element");

let state: StateMessage | null = null;
let lobby: LobbyMessage | null = null;
let talk: TalkEntry[] = [];
let notice = "";
let connection: Connection = "connecting";

const ctx: Context = {
  get state() {
    return state;
  },
  get lobby() {
    return lobby;
  },
  get talk() {
    return talk;
  },
  get notice() {
    return notice;
  },
  get connection() {
    return connection;
  },
  setNotice(text: string) {
    notice = text;
    draw();
  },
  redraw: () => draw(),
};
const draw = () => render(root, ctx);

connect({
  onLobby(next) {
    lobby = next;
    state = null;
    talk = [];
    notice = "";
    draw();
  },
  onState(next) {
    state = next;
    lobby = null;
    notice = "";
    draw();
  },
  onTalk(next) {
    talk = next.messages;
    draw();
  },
  onProblem(reason) {
    notice = reason;
    draw();
  },
  onConnection(next) {
    connection = next;
    draw();
  },
});
draw();
