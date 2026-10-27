import { resolve } from "node:path";
import { defineConfig } from "vite";

// A static export. Every page is its own HTML entry; Vite emits external module scripts only
// (no inline scripts, which the content security policy forbids), and nothing is inlined as a
// data: URI, so the CSP needs no data: source either.
const pages = ["index", "result", "paper", "docs", "privacy", "terms", "run", "viewer", "404"];

export default defineConfig({
  base: "/",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    target: "es2022",
    assetsInlineLimit: 0,
    modulePreload: { polyfill: false },
    sourcemap: false,
    rollupOptions: { input: Object.fromEntries(pages.map((p) => [p, resolve(import.meta.dirname, `${p}.html`)])) },
  },
  worker: { format: "es" },
  server: { headers: { "Cross-Origin-Opener-Policy": "same-origin" } },
});
