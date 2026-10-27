// The null's replicates, behind the trees: what the search looks like re-grown on noise. Each
// replicate the audit returned (its own draws, `replicate_paths`) is drawn as streaks from the
// ground to every rule it held, at that rule's Sharpe on that replicate; a restart is a new
// streak beside it. They appear as the replay progresses.
import type { ReplicatePath } from "./types";

const NS = "http://www.w3.org/2000/svg";
const VW = 1600, VH = 900;

export interface StreakHandle { reveal(fraction: number): void; clear(): void }

export function drawStreaks(svg: SVGSVGElement, paths: ReplicatePath[], lo: number, hi: number): StreakHandle {
  svg.setAttribute("viewBox", `0 0 ${VW} ${VH}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMax slice");
  svg.setAttribute("aria-hidden", "true");
  svg.replaceChildren();
  const y = (s: number) => VH - 40 - ((s - lo) / (hi - lo)) * (VH * 0.78);
  const els: SVGPathElement[] = [];
  // a seeded scatter, so a replicate keeps its place from run to run
  const rnd = (i: number) => { const x = Math.sin(i * 91.17 + 3.7) * 43758.5453; return x - Math.floor(x); };
  paths.forEach((p, b) => {
    const x0 = rnd(b) * VW, slant = (rnd(b + 500) - 0.5) * 0.9;     // up to about 24 degrees either way
    let stem = 0, d = "", x = x0, prevY = VH - 40;
    p.steps.forEach((s, i) => {
      if (s.action === "restart" || i === 0) {
        if (i > 0) stem++;
        x = x0 + stem * (8 + rnd(b + i) * 14);
        prevY = VH - 40;
        d += ` M${x.toFixed(1)} ${prevY.toFixed(1)}`;
      }
      const ny = y(s.sharpe), nx = x + slant * (prevY - ny) + (rnd(b * 31 + i) - 0.5) * 16;
      d += ` Q${(x + (nx - x) * 0.2).toFixed(1)} ${((prevY + ny) / 2).toFixed(1)} ${nx.toFixed(1)} ${ny.toFixed(1)}`;
      x = nx; prevY = ny;
    });
    const path = document.createElementNS(NS, "path");
    path.setAttribute("d", d.trim());
    svg.appendChild(path);
    els.push(path);
  });
  return {
    reveal: (fraction) => els.forEach((e, i) => e.classList.toggle("on", i < Math.round(fraction * els.length))),
    clear: () => els.forEach((e) => e.classList.remove("on")),
  };
}
