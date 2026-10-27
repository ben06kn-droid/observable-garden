// Leaves falling slowly behind the text: a few, calm, continuous. Reduced motion shows them still.
// Positions and timings go through CSS custom properties (CSSOM), so no inline style attribute is
// written and the content security policy needs no 'unsafe-inline'.
const NS = "http://www.w3.org/2000/svg";
const SHAPE = "M0 -9 C5 -6 7 0 0 9 C-7 0 -5 -6 0 -9 Z M0 -9 L0 9";

export function leaves(box: HTMLElement, n = 14) {
  box.replaceChildren();
  const rnd = (i: number) => { const x = Math.sin(i * 51.37 + 9.1) * 43758.5453; return x - Math.floor(x); };
  for (let i = 0; i < n; i++) {
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "-10 -10 20 20");
    svg.setAttribute("class", "leaf");
    svg.setAttribute("aria-hidden", "true");
    const p = document.createElementNS(NS, "path");
    p.setAttribute("d", SHAPE);
    svg.appendChild(p);
    const s = svg.style;
    s.setProperty("--x", `${(rnd(i) * 100).toFixed(1)}%`);
    s.setProperty("--y", `${(rnd(i + 40) * 90).toFixed(1)}%`);
    s.setProperty("--size", `${(12 + rnd(i + 80) * 12).toFixed(0)}px`);
    s.setProperty("--dur", `${(18 + rnd(i + 120) * 16).toFixed(1)}s`);
    s.setProperty("--delay", `${(-rnd(i + 160) * 30).toFixed(1)}s`);
    s.setProperty("--sway", `${(20 + rnd(i + 200) * 60).toFixed(0)}px`);
    s.setProperty("--spin", `${(rnd(i + 240) > 0.5 ? 1 : -1) * (180 + rnd(i + 280) * 360)}deg`);
    box.appendChild(svg);
  }
}
