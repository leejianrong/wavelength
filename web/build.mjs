// Compiles src/main.ts (and what it imports) to the one file the Python server serves.
import { build } from "esbuild";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
await build({
  entryPoints: [join(here, "src/main.ts")],
  outfile: join(here, "../src/wavelength/web/static/app.js"),
  bundle: true,
  format: "esm",
  target: "es2022",
  sourcemap: true,
  logLevel: "info",
});
