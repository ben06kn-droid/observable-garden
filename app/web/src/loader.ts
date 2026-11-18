// The loading screen: white, a ring that draws itself, is cut across and folds into a B (src/styles/loader.css
// holds the drawing and its timing), and a box (a rectangular prism) bottom left that fills with solid black in proportion to
// what has really loaded. The fill only ever rises and moves smoothly between updates. It always plays to the
// finished B (3 s), holds the B still until loading is done, then slides the whole screen up (600 ms) to reveal
// the site beneath. Shown once per browser session. Reduced motion: a still navy B and the box, then a plain cut.
import "./styles/loader.css";

const SEEN = "qx-loader-seen";
const FORMED_MS = 3000;
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;

const MARK = `<svg class="mark" viewBox="0 0 160 160" aria-hidden="true"><g class="all">
  <circle class="ring" cx="80" cy="80" r="52" pathLength="1"/>
  <g class="half ld-top"><path d="M 28 80 A 52 52 0 0 1 132 80"/></g>
  <g class="half ld-bottom"><path d="M 132 80 A 52 52 0 0 1 28 80"/></g>
  <line class="cut" x1="20" y1="80" x2="140" y2="80" pathLength="1"/>
</g></svg>
<svg class="tank" viewBox="-1 -15 78 400" aria-hidden="true">
  <defs><clipPath id="ld-box"><polygon points="0,0 20,-14 76,-14 76,370 56,384 0,384"/></clipPath></defs>
  <g clip-path="url(#ld-box)"><polygon class="level" points="0,0 20,-14 76,-14 76,520 0,520"/></g>
  <path class="edge" d="M 0 0 H 56 V 384 H 0 Z M 0 0 L 20 -14 H 76 L 56 0 M 76 -14 V 370 L 56 384"/>
</svg>`;

export class Loader {
  readonly el: HTMLElement;
  private target = 0; private shown = 0; private raf = 0; private last = 0;
  private formed: Promise<void>;
  private filled: () => void = () => {}; private full: Promise<void>;

  /** whether the screen has already played in this browser session (later visits go straight to the site) */
  static seen(): boolean { try { return sessionStorage.getItem(SEEN) === "1"; } catch { return false; } }

  constructor(host: HTMLElement = document.body) {
    this.el = document.createElement("div");
    this.el.className = "loader";
    this.el.setAttribute("role", "progressbar"); this.el.setAttribute("aria-label", "Loading the site");
    this.el.setAttribute("aria-valuemin", "0"); this.el.setAttribute("aria-valuemax", "100"); this.el.setAttribute("aria-valuenow", "0");
    this.el.innerHTML = MARK;
    host.append(this.el);
    this.formed = reduce ? Promise.resolve() : new Promise((r) => window.setTimeout(r, FORMED_MS));
    this.full = new Promise((r) => { this.filled = r; });
  }

  /** what has really loaded, 0-1; the box never empties back */
  progress(p: number) {
    this.target = Math.max(this.target, Math.min(1, Math.max(0, p)));
    this.el.setAttribute("aria-valuenow", String(Math.round(this.target * 100)));
    if (!this.raf) { this.last = performance.now(); this.raf = requestAnimationFrame(this.tick); }
  }

  private tick = (t: number) => {
    this.raf = 0;
    const dt = Math.min(0.05, (t - this.last) / 1000); this.last = t;
    // the level eases toward what has loaded (about 0.3 s to close the gap), so it rises smoothly between updates
    this.shown += (this.target - this.shown) * (reduce ? 1 : 1 - Math.exp(-10 * dt));
    if (this.target - this.shown < 0.002) this.shown = this.target;
    this.el.style.setProperty("--ld-p", this.shown.toFixed(4));
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
