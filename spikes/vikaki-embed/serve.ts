// Serves host.html on :8890 until stopped, so you can open it in your own browser. Run with VIKAKI_DIR set (see README).
import { createRequire } from "node:module";
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { execFile } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const req = createRequire(join(process.env.VIKAKI_DIR!, "packages/e2e/package.json"));
const { transformSync } = req("esbuild") as typeof import("esbuild");
createServer((rq, rs) => {
  if (rq.method === "POST" && rq.url === "/say") {
    const py = join(process.env.VIKAKI_DIR!, "clients/python");
    execFile("uv", ["run", "--with", py, "python", join(here, "drive.py"), "--only", "first"], { timeout: 60000 }, (err, out, errOut) => rs.end(err ? `error: ${errOut || err.message}` : out));
    return;
  }
  const path = (rq.url ?? "/").split("?")[0];
  rs.setHeader("content-type", path === "/host.js" ? "text/javascript" : "text/html");
  rs.end(path === "/host.js" ? transformSync(readFileSync(join(here, "host.ts"), "utf8"), { loader: "ts" }).code : readFileSync(join(here, "host.html")));
}).listen(8890, "0.0.0.0", () => console.log("host page: http://127.0.0.1:8890/?allow=autoplay   (?allow=none to omit the allow attribute)"));
