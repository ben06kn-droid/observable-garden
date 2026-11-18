// The Contact page (contact.html; DESIGN.md 3, contact): a separate document, outside the one-page scroll, opened from
// the menu. It opens behind the loading screen every time, played in full (the ring, the cut, the fold into the B, the
// box and the counter, then the slide up), even when the screen has already been shown in this session: the page never
// loads public/loader-early.js, so the screen never starts formed. Reduced motion: the still B and a plain cut
// (src/loader.ts). The box follows what has really loaded: the page's styles, its fonts, then the page itself.
// Kept simple, to take animations later: the headline and the four lines are plain markup in the page.
import "../common";
import "../styles/contact.css";
import { Loader } from "../loader";

const loader = new Loader(document.querySelector<HTMLElement>(".loader"));
loader.progress(0.3);                                         // the page and its styles are in
void document.fonts.ready.then(() => loader.progress(0.8));   // its faces
const done = () => { loader.progress(1); void loader.finish(); };
if (document.readyState === "complete") done(); else window.addEventListener("load", done, { once: true });
