// The Contact page (contact.html; DESIGN.md 3, contact): a separate document, outside the one-page scroll, opened from
// the menu. It opens behind the loading screen every time, played in full (the ring, the cut, the fold into the B, the
// box and the counter, then the white screen slides up to the blue page), even when the screen has already been shown
// in this session: the page never loads public/loader-early.js, so the screen never starts formed. Reduced motion: the
// still B and a plain cut (src/loader.ts). The box follows what has really loaded: the styles, the fonts, the fan, the
// page.
//
// Behind the text, the run section's fan of paths (src/fan.ts, reused): `full`, every path complete across the page and
// still from the first frame. On a desktop with motion the run section's cursor tail runs over it (the shared
// src/cursorwake.ts through the fan, same shape, timing and behaviour): the paths bend and settle back; the white ones
// take rose gold where run's turn red, the silver ones bend and keep their colour. Behind the headline, the three lines
// and the footer the paths are dimmed (white text 4.5:1 or more) and there is no glossy trace. Phone: the fan still, no
// tail. Reduced motion: the fan still, no tail.
import "../common";
import "../styles/contact.css";
import { reduceMotion } from "../common";
import { wakeWanted } from "../cursorwake";
import { Fan, type FanRect } from "../fan";
import { Loader } from "../loader";

const loader = new Loader(document.querySelector<HTMLElement>(".loader"));
loader.progress(0.3);                                         // the page and its styles are in

const host = document.createElement("div");
host.className = "ct-fan"; host.setAttribute("aria-hidden", "true");
document.body.prepend(host);
const phone = matchMedia("(max-width: 812px)");
// what the paths dim behind: the letters themselves (not their boxes) of the headline, the three lines and the footer,
// and no glossy trace there
const glyphs = () => [...document.querySelectorAll(".ct-h, .ct-list a, .foot > span, .foot nav")].map((el) => ({ el, keep: 0.12, trace: 0 }));
// the links' arrows (↗, ↓) are drawn by CSS, not text: a small box over each
function masks(): FanRect[] {
  const out: FanRect[] = [], range = document.createRange();
  for (const a of document.querySelectorAll<HTMLElement>(".ct-list a[target=_blank], .ct-list a.ct-dl")) {
    range.selectNodeContents(a); const t = range.getBoundingClientRect(), r = a.getBoundingClientRect();
    if (r.right - t.right > 1) out.push({ x: t.right, y: t.top + scrollY, w: r.right - t.right + 4, h: t.height, keep: 0.12, trace: 0 });
  }
  return out;
}
let fan: Fan | null = null;
function build() {
  fan?.destroy();
  fan = new Fan(host, { full: true, reduce: reduceMotion, seed: 5, wake: !phone.matches && wakeWanted(),
    region: () => ({ top: 0, bottom: document.documentElement.scrollHeight }),
    reach: () => innerWidth * 1.45,   // the fade before the reach falls past the window's right edge: every path runs across
    masks, glyphs });
}
let t = 0;
addEventListener("resize", () => { window.clearTimeout(t); t = window.setTimeout(build, 150); });

void document.fonts.ready.then(() => {
  loader.progress(0.6);                                       // its faces; the text has its final layout for the masks
  build();
  loader.progress(0.85);
  const done = () => { loader.progress(1); void loader.finish(); };
  if (document.readyState === "complete") done(); else window.addEventListener("load", done, { once: true });
});
