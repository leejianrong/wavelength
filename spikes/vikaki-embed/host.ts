// Throwaway host page: embeds vikaki's avatar page from another origin and logs everything we can observe from outside it.
const q = new URLSearchParams(location.search);
const hub = q.get("hub") ?? "http://127.0.0.1:8787";
const allow = q.get("allow") ?? "autoplay"; // "autoplay" or "none"
const seats = q.get("seats") ?? "2";
const frame = document.getElementById("avatar") as HTMLIFrameElement;
const log = document.getElementById("log") as HTMLElement;
const note = (s: string) => {
  log.textContent += `${new Date().toISOString().slice(11, 23)} ${s}\n`;
};

if (allow === "autoplay") frame.setAttribute("allow", "autoplay");
frame.src = `${hub}/avatar?seats=${seats}&live=1&hud=0&bg=fff1e8`;
frame.addEventListener("load", () => note("iframe load event"));
window.addEventListener("message", (e) => note(`message from ${e.origin}: ${JSON.stringify(e.data).slice(0, 120)}`));
document.getElementById("sound")?.addEventListener("click", () => {
  note("parent click");
  frame.contentWindow?.postMessage({ type: "unlock" }, "*"); // nothing listens for this yet (VIK-66)
});

// Spike-only: the host server runs the Python driver (drive.py) so the autoplay check needs no other tool. In the real game the
// Python game server is the driver; the browser never talks to the hub itself (the hub refuses other origins).
document.getElementById("say")?.addEventListener("click", async () => {
  note("asking the host server to speak a line from seat 1");
  const r = await fetch("/say", { method: "POST" });
  note(`driver: ${(await r.text()).trim().slice(0, 200)}`);
});
