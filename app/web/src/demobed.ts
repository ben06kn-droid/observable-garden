// The flower bed for the repeated searches (DESIGN.md 3, demo): small flowers in the tree's thin blue lines growing
// along its ground line while the gate repeats the search. Decoration that reads nothing from the gate: it keeps its
// own clock (the old bed's: from its start, flower i begins at its own moment over the first 4.5 s, its stem grows over
// 1.6 s on an eased curve and its head opens over 1.8 s), so it blooms at the same pace however fast the gate runs.
// Each flower's place, height and lean come from the run's id, so a run's bed looks the same on every visit. Drawn
// into one canvas in the tree's own frame (its ground line and scale), clear of the trunk's foot; painted on every
// other frame while it grows, and not at all otherwise.
import { hash } from "./heads";

interface Flower { x: number; h: number; lean: number; r: number; s0: number; open: number; petals: number }

export interface Bed { reset(id: string, half: number): void; start(): void; finish(): void; clear(): void; paint(): void }

export function makeBed(cv: HTMLCanvasElement, frame: () => ((x: number, y: number) => [number, number]) | null, n = 96): Bed {
  let flowers: Flower[] = [], t0 = 0, running = false, odd = false, state: "off" | "growing" | "done" = "off";
  const START = 4.5, GROW = 1.6, OPEN = 1.8, END = START + 1.2 + 0.8 + OPEN;
  const ease = (x: number) => 1 - Math.pow(1 - Math.max(0, Math.min(1, x)), 3);
  const smooth = (x: number) => { const t = Math.max(0, Math.min(1, x)); return t * t * (3 - 2 * t); };

  function reset(id: string, half: number) {
    flowers = [];
    for (let i = 0; i < n; i++) {
      const hs = hash(`${id}:${i}`), q = (k: number) => ((hs >>> k) % 1000) / 1000;
      // spread along the ground either side of the foot, thinning toward the ends; nothing within 22 units of the trunk
      const side = hs % 2 ? 1 : -1, au = Math.pow(q(3), 1.25), x = side * (22 + au * (half - 34));
      flowers.push({ x, h: (9 + 17 * q(10)) * (1 - 0.45 * au), lean: side * (2 + 9 * q(7)) * au, r: 1.6 + 1.3 * q(16),
        s0: q(4) * START, open: 1.2 + 0.8 * q(13), petals: 5 + (hs % 2) });
    }
    state = "off"; running = false; clear();
  }
  function clear() { const c = cv.getContext("2d"); c?.setTransform(1, 0, 0, 1, 0, 0); c?.clearRect(0, 0, cv.width, cv.height); }
  function start() {
    t0 = performance.now(); state = "growing";
    if (running) return;
    running = true;
    const tick = (now: number) => {
      const t = (now - t0) / 1000;
      odd = !odd;
      if (odd || t > END) draw(t);
      if (t <= END + 0.05 && state === "growing") requestAnimationFrame(tick); else { running = false; if (state === "growing") state = "done"; }
    };
    requestAnimationFrame(tick);
  }
  function finish() { state = "done"; running = false; draw(60); }
  function paint() { if (state === "done") draw(60); else if (state === "off") clear(); }

  function draw(t: number) {
    const map = frame(), c = cv.getContext("2d");
    if (!map || !c) return;
    const r = cv.getBoundingClientRect(), dpr = Math.min(devicePixelRatio || 1, 2);
    const W = Math.ceil(r.width * dpr), H = Math.ceil(r.height * dpr);
    if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; }
    c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, W, H);
    // svg units → px: the frame maps to the canvas's own box
    const [ox, oy] = map(0, 0), [ux] = map(1, 0), k = (ux - ox);
    c.setTransform(dpr * k, 0, 0, dpr * k, dpr * ox, dpr * oy);
    c.lineCap = "round";
    const blue = getComputedStyle(cv).getPropertyValue("--blue").trim() || "#44b8ff";
    c.strokeStyle = blue;
    for (const fl of flowers) {
      const g = ease((t - fl.s0) / GROW);
      if (g <= 0) continue;
      const op = smooth((t - fl.s0 - fl.open) / OPEN);
      const top: [number, number] = [fl.x + fl.lean * g, -fl.h * g];
      // the stem: a fine curve, a little bowed
      c.globalAlpha = 0.5; c.lineWidth = 0.55 / 1;
      c.beginPath(); c.moveTo(fl.x, 0); c.quadraticCurveTo(fl.x + fl.lean * 0.15 * g, -fl.h * 0.55 * g, top[0], top[1]); c.stroke();
      // the head: a ring of small petal loops, opening from a closed bud
      const rr = fl.r * (0.35 + 0.65 * op);
      c.globalAlpha = 0.55 + 0.35 * op; c.lineWidth = 0.5;
      if (op <= 0.02) { c.beginPath(); c.arc(top[0], top[1], 0.9, 0, Math.PI * 2); c.stroke(); continue; }
      for (let p = 0; p < fl.petals; p++) {
        const a = (p / fl.petals) * Math.PI * 2 - Math.PI / 2, cx = top[0] + Math.cos(a) * rr * 0.62, cy = top[1] + Math.sin(a) * rr * 0.62;
        c.beginPath(); c.ellipse(cx, cy, rr * 0.5, rr * 0.3, a, 0, Math.PI * 2); c.stroke();
      }
    }
    c.globalAlpha = 1;
  }
  return { reset, start, finish, clear, paint };
}
