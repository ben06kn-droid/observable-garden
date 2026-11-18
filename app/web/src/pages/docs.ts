// The docs page: reading first, in clear sky and glass (src/styles/docs.css), a link in the scroll chain
// (home → run → docs → Sancho). The contents sit beside the text on wide screens and fold above it on
// narrow ones, the current section marked; each code block has a copy button. Behind everything, the sky
// (src/sky.ts): a vivid ground with its light, the cursor's tail, and glass bubbles drifting up the margin.
import "../common";              // the shared stylesheet first, so the theme wins ties
import "../styles/docs.css";
import { fadeIn, settled } from "../chain";
import { reduceMotion } from "../common";
import { Sky } from "../sky";

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
  // and a comment (from " #" to the end of its line) in its own colour
  const words = (str: string) => str.split(/(\s+)/).map((w) => { if (!w || /^\s+$/.test(w)) return document.createTextNode(w); const t = document.createElement("span"); t.className = "t"; t.textContent = w; return t; });
  pre.replaceChildren(...src.split(/(\n)/).flatMap((line) => {
    const at = line.search(/(^|\s)#\s/);
    if (at < 0) return words(line);
    const c = document.createElement("span"); c.className = "c"; c.append(...words(line.slice(at)));
    return [...words(line.slice(0, at)), c];
  }));
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

// ---- the sky: the ground and its light, the tail, the bubbles in the lane right of the text (none on a phone)
const head = document.querySelector<HTMLElement>(".top");
const sheet = document.querySelector<HTMLElement>(".sheet") ?? text;
// started once the page has arrived (src/chain.ts: after a carry's transition, never in a prerender); until then
// docs.css draws its first frame (the gradient and the light fields) as the stand-in, and the sky fades in over it
let sky: Sky | null = null;
const makeSky = () => new Sky(document.body, {
  reduce: reduceMotion,
  small: () => phone.matches,
  lane: () => {
    if (phone.matches) return null;
    const r = sheet.getBoundingClientRect(), gap = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--gap")) || 24;
    // the bubbles may drift 44px in under the pane: behind the glass, within its 48px padding, short of the text
    return { x0: Math.round(r.right + gap), x1: innerWidth, top: head?.getBoundingClientRect().bottom ?? 76, bottom: innerHeight, under: Math.round(gap + 44) };
  },
  // the tail runs behind the glass but never behind the text: the sheet less its padding
  text: () => { const r = sheet.getBoundingClientRect(), pad = parseFloat(getComputedStyle(sheet).paddingLeft) || 0; return { x: r.left + pad, y: r.top + pad, w: r.width - 2 * pad, h: r.height - 2 * pad }; },
});
void settled.then(() => {
  sky = makeSky();
  sky.watch(document.querySelector<HTMLElement>(".carry-next"), document.querySelector<HTMLElement>(".foot"));
  void fadeIn(document.querySelector("canvas.sky"));
});
// ---- the light on the glass's edge follows the cursor: within about 250px of it, a soft point of full white
// slides along the rim (only the border); it settles in 300ms when the cursor goes. Not by touch, not on a
// phone, not under reduced motion.
if (!reduceMotion && sheet !== text) {
  let lx = 0, ly = 0, on = 0, raf = 0;
  const apply = () => {
    raf = 0;
    sheet.style.setProperty("--lx", `${lx}px`); sheet.style.setProperty("--ly", `${ly}px`); sheet.style.setProperty("--la", String(on));
  };
  window.addEventListener("pointermove", (e: PointerEvent) => {
    if (e.pointerType === "touch" || phone.matches) return;
    const r = sheet.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
    // how far the cursor is from the rim, inside or out
    const inside = x >= 0 && y >= 0 && x <= r.width && y <= r.height;
    const d = inside ? Math.min(x, y, r.width - x, r.height - y) : Math.hypot(Math.max(0, -x, x - r.width), Math.max(0, -y, y - r.height));
    lx = x; ly = y; on = d < 250 ? 1 : 0;
    if (!raf) raf = requestAnimationFrame(apply);
  }, { passive: true });
  document.documentElement.addEventListener("pointerleave", () => { on = 0; if (!raf) raf = requestAnimationFrame(apply); }, { passive: true });
}
let resizeT = 0;
addEventListener("resize", () => { window.clearTimeout(resizeT); resizeT = window.setTimeout(() => sky?.layout(), 150); });
void document.fonts.ready.then(() => sky?.layout());
