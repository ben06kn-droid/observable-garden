// The docs page: reading first, in clear sky and glass (src/styles/docs.css), a link in the scroll chain
// (home → run → docs → Sancho). The contents sit beside the text on wide screens and fold above it on
// narrow ones, the current section marked; each code block has a copy button; glass bubbles drift up the
// margin (src/bubbles.ts) and wobble where the cursor passes.
import "../common";              // the shared stylesheet first, so the theme wins ties
import "../styles/docs.css";
import "../chain";
import { reduceMotion } from "../common";
import { Bubbles } from "../bubbles";

const text = document.querySelector<HTMLElement>(".docs-text")!;
const wide = matchMedia("(min-width: 1241px)"), phone = matchMedia("(max-width: 812px)");

// ---- contents: open beside the text on a wide screen; folded above it on a narrow one
const toc = document.querySelector<HTMLDetailsElement>(".toc details")!;
const fold = () => { toc.open = wide.matches; };
fold(); wide.addEventListener("change", fold);
// the current section: the last heading that has passed the top of the reading area
const links = new Map([...document.querySelectorAll<HTMLAnchorElement>(".toc a")].map((a) => [a.hash.slice(1), a]));
const heads = [...text.querySelectorAll<HTMLElement>("h2[id], h3[id]")].filter((h) => links.has(h.id));
let current = "";
const mark = () => {
  const line = innerHeight * 0.3;
  let id = heads[0]?.id ?? "";
  for (const h of heads) if (h.getBoundingClientRect().top <= line) id = h.id;
  if (id === current) return;
  links.get(current)?.removeAttribute("aria-current"); links.get(id)?.setAttribute("aria-current", "true"); current = id;
};
let markRaf = 0;
addEventListener("scroll", () => { if (!markRaf) markRaf = requestAnimationFrame(() => { markRaf = 0; mark(); }); }, { passive: true });
mark();
// on a narrow screen, choosing a section folds the contents again
toc.addEventListener("click", (e) => { if (!wide.matches && (e.target as HTMLElement).closest("a")) toc.open = false; });

// ---- code on glass, each block with a copy button (the block itself stays plain text for selection)
for (const pre of text.querySelectorAll<HTMLPreElement>("pre.cmd")) {
  // each word of the command kept whole when the line wraps (the text, and what is copied, unchanged)
  const src = pre.textContent ?? "";
  pre.replaceChildren(...src.split(/(\s+)/).map((w) => { if (!w || /^\s+$/.test(w)) return document.createTextNode(w); const t = document.createElement("span"); t.className = "t"; t.textContent = w; return t; }));
  const panel = document.createElement("div"); panel.className = "glass code";
  pre.replaceWith(panel); panel.append(pre);
  const b = document.createElement("button"); b.type = "button"; b.className = "copy"; b.textContent = "Copy";
  b.setAttribute("aria-label", "Copy this command");
  let t = 0;
  b.addEventListener("click", async () => {
    const done = (msg: string) => { b.textContent = msg; window.clearTimeout(t); t = window.setTimeout(() => { b.textContent = "Copy"; }, 1400); };
    try { await navigator.clipboard.writeText(src); done("Copied"); }
    catch { const r = document.createRange(); r.selectNodeContents(pre); const s = getSelection(); s?.removeAllRanges(); s?.addRange(r); done("Selected"); }
  });
  panel.append(b);
}

// ---- tables: their roles set explicitly, so a phone's card layout (docs.css) keeps them a table to a reader
for (const t of text.querySelectorAll("table")) {
  t.setAttribute("role", "table");
  for (const tr of t.querySelectorAll("tr")) {
    tr.setAttribute("role", "row");
    const header = tr.querySelectorAll("th").length > 1;
    for (const c of tr.children) c.setAttribute("role", c.tagName === "TH" ? (header ? "columnheader" : "rowheader") : "cell");
  }
}

// ---- the bubbles: in the lane right of the text, below the header; none on a phone
const head = document.querySelector<HTMLElement>(".top");
const bubbles = new Bubbles(document.body, {
  reduce: reduceMotion,
  lane: () => {
    if (phone.matches) return null;
    const r = text.getBoundingClientRect(), gap = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--gap")) || 24;
    return { x0: Math.round(r.right + gap), x1: innerWidth, top: head?.getBoundingClientRect().bottom ?? 76, bottom: innerHeight };
  },
});
bubbles.watch(document.querySelector<HTMLElement>(".carry-next"), document.querySelector<HTMLElement>(".foot"));
let resizeT = 0;
addEventListener("resize", () => { window.clearTimeout(resizeT); resizeT = window.setTimeout(() => bubbles.layout(), 150); });
void document.fonts.ready.then(() => bubbles.layout());
