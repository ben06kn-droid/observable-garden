import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig, type Plugin } from "vite";
import { LOADER } from "./src/loader-mark";

// A static export. Every page is its own HTML entry; Vite emits external module scripts only
// (no inline scripts, which the content security policy forbids), and nothing is inlined as a
// data: URI, so the CSP needs no data: source either.
// the pinned Pyodide release: its files are served from /pyodide/<version>/
const PYODIDE = JSON.parse(readFileSync(resolve(import.meta.dirname, "public/pyodide/MANIFEST.json"), "utf8")).pyodide;

const pages = ["index", "demo", "result", "docs", "privacy", "terms", "run", "share", "viewer", "sancho", "404", "loader"];

// The one-page site: home and run (docs and Sancho to follow) are sections of one document, built once behind the
// loading screen and kept alive. Every address of it (/, /run.html) is the same document with its own title,
// description and starting section (data-start); this writes in what they share, in order: the loading screen
// (on screen from the first frame), the header, one backdrop per section (src/onepage/boot.ts crossfades them by
// scroll position) and the sections, from src/onepage/*.html.
const SECTIONS = ["home", "run"];
const part = (n: string) => readFileSync(resolve(import.meta.dirname, "src/onepage", `${n}.html`), "utf8");
function onepage(): Plugin {
  return {
    name: "onepage",
    transformIndexHtml: { order: "pre", handler(html) {
      const at = html.indexOf("<!-- onepage");
      if (at < 0) return html;
      const end = html.indexOf("-->", at) + 3;
      const backdrops = `<div class="backdrops" aria-hidden="true">${SECTIONS.map((n) => `<div class="backdrop" data-for="${n}" data-theme="${n}"></div>`).join("")}</div>`;
      const body = `${LOADER}\n${part("header")}${backdrops}\n<main id="main">\n${SECTIONS.map(part).join("")}</main>\n`;
      return html.slice(0, at) + body + html.slice(end);
    } },
  };
}

export default defineConfig({
  plugins: [onepage()],
  base: "/",
  define: { __PYODIDE_VERSION__: JSON.stringify(PYODIDE) },
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
