// Things falling slowly over the background: yellow leaves released from page one's trees, pink
// cherry-blossom petals from page two's (pink always, also inside a run). Continuous and calm; reduced
// motion shows them still, scattered along their paths. They animate transform only (translate and
// rotate, on the compositor): the start is a static left/top, and the fall distance is set in pixels
// from the box's height, so no frame needs layout or paint. Positions and timings go through CSS
// custom properties set with the CSSOM, so no inline style attribute is written and the content
// security policy needs no 'unsafe-inline'.
const NS = "http://www.w3.org/2000/svg";
const SHAPES = {
  leaf: "M0 -9 C5 -6 7 0 0 9 C-7 0 -5 -6 0 -9 Z M0 -9 L0 9",
  // five-notched cherry petal: rounded, with the notch at its tip
  petal: "M0 9 C-6 6 -8 -2 -4 -7 C-2.5 -9 -1 -9 0 -6.5 C1 -9 2.5 -9 4 -7 C8 -2 6 6 0 9 Z",
};

export interface FallOptions {
  n: number;
  kind: "leaf" | "petal";
  sources?: { x: number; y: number }[];    // where each one starts, as fractions of the box (else above it)
  seed?: number;
}

export function fall(box: HTMLElement, o: FallOptions) {
  box.replaceChildren();
  const H = box.clientHeight || window.innerHeight;
  const seed = o.seed ?? 3;
  const rnd = (i: number) => { const x = Math.sin(i * 51.37 + seed * 9.1) * 43758.5453; return x - Math.floor(x); };
  for (let i = 0; i < o.n; i++) {
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "-10 -10 20 20");
    svg.setAttribute("class", o.kind);
    svg.setAttribute("aria-hidden", "true");
    const p = document.createElementNS(NS, "path");
    p.setAttribute("d", SHAPES[o.kind]);
    svg.appendChild(p);
    const src = o.sources?.length ? o.sources[Math.floor(rnd(i + 7) * o.sources.length)] : null;
    const x0 = src ? src.x * 100 : rnd(i) * 100, y0 = src ? src.y * 100 : -6 - rnd(i + 3) * 10;
    const s = svg.style;
    s.setProperty("--x", `${x0.toFixed(2)}%`);
    s.setProperty("--y0", `${y0.toFixed(2)}%`);
    s.setProperty("--fall", `${((104 - y0) / 100 * H).toFixed(0)}px`);         // to just below the box
    s.setProperty("--hold", `${((rnd(i + 40) * (100 - y0)) / 100 * H).toFixed(0)}px`);   // where reduced motion holds it
    s.setProperty("--size", `${(o.kind === "petal" ? 9 + rnd(i + 80) * 9 : 11 + rnd(i + 80) * 11).toFixed(0)}px`);
    s.setProperty("--dur", `${(16 + rnd(i + 120) * 18).toFixed(1)}s`);
    s.setProperty("--delay", `${(-rnd(i + 160) * 34).toFixed(1)}s`);
    s.setProperty("--sway", `${(18 + rnd(i + 200) * 56).toFixed(0)}px`);
    s.setProperty("--spin", `${(rnd(i + 240) > 0.5 ? 1 : -1) * (160 + rnd(i + 280) * 380)}deg`);
    box.appendChild(svg);
  }
}

/** Crown points of an svg drawing (viewBox coordinates as fractions) mapped to fractions of `box`,
 *  so that what falls starts where the crowns actually are on screen. */
export function onScreen(svg: SVGSVGElement, box: HTMLElement, pts: { x: number; y: number }[]) {
  const vb = svg.viewBox.baseVal, m = svg.getScreenCTM(), b = box.getBoundingClientRect();
  if (!m || !b.width || !b.height) return pts;
  const p = svg.createSVGPoint();
  return pts.map((t) => {
    p.x = t.x * vb.width; p.y = t.y * vb.height;
    const q = p.matrixTransform(m);
    return { x: (q.x - b.left) / b.width, y: (q.y - b.top) / b.height };
  }).filter((t) => t.x > -0.02 && t.x < 1.02 && t.y > -0.05 && t.y < 1);
}
