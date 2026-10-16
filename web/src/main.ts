import { connect, type Connection } from "./api.ts";
import type { StateMessage } from "./types.ts";
import { render } from "./view.ts";

const root = document.getElementById("app");
if (!root) throw new Error("no #app element");

let state: StateMessage | null = null;
let notice = "";
let connection: Connection = "connecting";

const draw = () => render(root, { state, notice, connection, setNotice });
function setNotice(text: string) {
  notice = text;
  draw();
}

connect({
  onState(next) {
    state = next;
    notice = "";
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
