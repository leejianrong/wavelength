// Builds src/main.ts to the two files the Python server serves: static/app.js and static/app.css
// (plus the self-hosted fonts in static/assets/). index.html in static/ is a plain, tracked file.
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";

export default defineConfig({
  base: "/static/",
  plugins: [svelte()],
  build: {
    outDir: "../src/wavelength/web/static",
    emptyOutDir: false,
    sourcemap: true,
    assetsInlineLimit: 0,
    cssCodeSplit: false,
    rolldownOptions: {
      input: "src/main.ts",
      output: {
        entryFileNames: "app.js",
        // The one stylesheet is app.css next to app.js; the fonts it names go in assets/.
        assetFileNames: (asset) => (asset.names.some((n) => n.endsWith(".css")) ? "app[extname]" : "assets/[name][extname]"),
      },
    },
  },
});
