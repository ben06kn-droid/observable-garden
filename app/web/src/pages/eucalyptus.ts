// The Eucalyptus section of the one-page site (src/onepage/eucalyptus.html; eucalyptus.html opens on it): "Coming
// soon" on a lime ground, the menu and the footer in its colours (src/styles/eucalyptus.css), and Sancho's cursor tail,
// one to one (src/trace.ts), drawn in the section's backdrop, never behind the text or the footer.
import "../common";              // the shared stylesheet first, so the theme wins ties
import "../styles/eucalyptus.css";
import { onBackdrop, section } from "../onepage/boot";
import { reduceMotion } from "../common";
import { Trace } from "../trace";

const root = section("eucalyptus"), phone = matchMedia("(max-width: 812px)");
const backdrop = document.querySelector<HTMLElement>('.backdrop[data-for="eucalyptus"]');
if (root && backdrop) {
  const box = (e: Element | null) => { if (!e) return null; const r = e.getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; };
  const trace = new Trace(backdrop, { reduce: reduceMotion, small: () => phone.matches,
    // the text it keeps clear of: the label and the title together, and the footer
    text: () => { const l = box(root.querySelector(".euc-label")), t = box(root.querySelector(".euc-title")), f = box(root.querySelector(".foot"));
      const head = l && t ? { x: Math.min(l.x, t.x), y: l.y, w: Math.max(l.x + l.w, t.x + t.w) - Math.min(l.x, t.x), h: t.y + t.h - l.y } : null;
      return [head, f].filter((b): b is NonNullable<typeof b> => !!b); } });
  onBackdrop("eucalyptus", (v) => trace.setActive(v));
}
