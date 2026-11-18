// The loading screen: white, a ring that draws itself, is cut across and folds into a B (src/styles/loader.css
// holds the drawing and its timing), and a box (a rectangular prism) bottom left that fills with solid black in proportion to
// what has really loaded. The fill only ever rises and moves smoothly between updates. It always plays to the
// finished B (1.5 s), holds the B still until loading is done, then slides the whole screen up (600 ms) to reveal
// the site beneath. Shown once per browser session. Reduced motion: a still navy B and the box, then a plain cut.
// Beside the box, a percent counter in block numerals (src/loader-mark.ts): the same eased value as the fill, as a
// whole number, so the two always agree; it only rises, and reads 100 exactly when the box is full. The screen is
// one progressbar whose value is that number.
import "./styles/loader.css";
import { COUNTER, counterDigits, MARK } from "./loader-mark";

const SEEN = "qx-loader-seen";
const FORMED_MS = 1500;          // the B's length (ring 0-400 ms, cut 400-700, fold 700-1500)
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;



export class Loader {
  readonly el: HTMLElement;
  private target = 0; private shown = 0; private raf = 0; private last = 0; private snap = false;
  private digits: SVGPathElement | null = null; private count = -1;
  private formed: Promise<void>;
  private filled: () => void = () => {}; private full: Promise<void>;

  /** whether the screen has already played in this browser session (later visits go straight to the site) */
  static seen(): boolean { try { return sessionStorage.getItem(SEEN) === "1"; } catch { return false; } }

  /** `existing`: the screen already in the page (the one-page site writes it into its HTML); otherwise one is made.
   *  `formed`: the B is already in place and there is no minimum time (a rebuild later in the session: public/loader-early.js) */
  constructor(existing?: HTMLElement | null, { formed = false } = {}) {
    if (existing) this.el = existing;
    else {
      this.el = document.createElement("div");
      this.el.className = "loader";
      this.el.setAttribute("role", "progressbar"); this.el.setAttribute("aria-label", "Loading the site");
      this.el.setAttribute("aria-valuemin", "0"); this.el.setAttribute("aria-valuemax", "100"); this.el.setAttribute("aria-valuenow", "0");
      this.el.setAttribute("aria-valuetext", "0%");
      this.el.innerHTML = MARK + COUNTER;
      document.body.append(this.el);
    }
    if (formed) this.el.classList.add("formed");
    this.digits = this.el.querySelector<SVGPathElement>(".count .digits");
    this.snap = formed;
    // the minimum time is the whole B: the ring, the cut and the fold, played to their end. It waits on the drawing's
    // own animations (they start with the screen's first frame, which can come a few hundred ms after the page began:
    // a timer from the page's start cut the fold short by 100-380 ms, measured 2026-11-18). A backstop of twice the
    // B's length keeps a stalled animation (a hidden tab) from holding the site. A rebuild has no minimum.
    const mark = this.el.querySelector(".mark"), drawing = mark?.getAnimations({ subtree: true }) ?? [];
    this.formed = reduce || formed ? Promise.resolve()
      : Promise.race([Promise.all(drawing.map((a) => a.finished.catch(() => undefined))).then(() => undefined), new Promise<void>((r) => window.setTimeout(r, 2 * FORMED_MS))]);
    this.full = new Promise((r) => { this.filled = r; });
  }

  /** what has really loaded, 0-1; the box never empties back */
  progress(p: number) {
    this.target = Math.max(this.target, Math.min(1, Math.max(0, p)));
    if (!this.raf) { this.last = performance.now(); this.raf = requestAnimationFrame(this.tick); }
  }

  private tick = (t: number) => {
    this.raf = 0;
    const dt = Math.min(0.05, (t - this.last) / 1000); this.last = t;
    // the level eases toward what has loaded (about 0.3 s to close the gap), so it rises smoothly between updates
    // (a rebuild later in the session lasts only as long as the rebuild: its box does not ease)
    this.shown += (this.target - this.shown) * (reduce || this.snap ? 1 : 1 - Math.exp(-10 * dt));
    if (this.target - this.shown < 0.002) this.shown = this.target;
    this.el.style.setProperty("--ld-p", this.shown.toFixed(4));
    // the counter: the fill's own value as a whole number (rounded down: 100 only when the box is full)
    const n = this.shown >= 1 ? 100 : Math.min(99, Math.floor(this.shown * 100));
    if (n > this.count) {
      this.count = n; this.digits?.setAttribute("d", counterDigits(n));
      this.el.setAttribute("aria-valuenow", String(n)); this.el.setAttribute("aria-valuetext", `${n}%`);
    }
    if (this.shown >= 1) this.filled();
    if (this.shown < this.target) this.raf = requestAnimationFrame(this.tick);
  };

  /** loading is complete: once the B has formed and the box is full, slide the screen away */
  async finish(): Promise<void> {
    this.progress(1);
    await Promise.all([this.formed, this.full]);
    try { sessionStorage.setItem(SEEN, "1"); } catch { /* private mode: it shows again next time */ }
    if (reduce) { this.el.remove(); return; }
    this.el.classList.add("leaving");
    await new Promise<void>((r) => { this.el.addEventListener("animationend", (e) => { if (e.animationName === "ld-leave") r(); }); window.setTimeout(r, 900); });
    this.el.remove();
  }
}
