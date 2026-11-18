// A preview of the loading screen (src/loader.ts) on its own page: a simulated load, uneven as a real one is, and a
// Replay button. window.__preview lets a script stop the screen at any moment for a frame sequence.
import "../common";
import "../styles/docs.css";
import { Loader } from "../loader";

const ms = Number(new URLSearchParams(location.search).get("ms") ?? 3600);
// what has "loaded" by time t (ms): bursts and stalls, as a real load is
const STEPS: [number, number][] = [[0, 0], [0.08, 0.1], [0.2, 0.18], [0.35, 0.22], [0.5, 0.47], [0.62, 0.52], [0.8, 0.83], [0.92, 0.9], [1, 1]];
const loaded = (t: number) => {
  const x = Math.max(0, Math.min(1, t / ms));
  for (let i = 1; i < STEPS.length; i++) if (x <= STEPS[i][0]) return STEPS[i - 1][1] + ((x - STEPS[i - 1][0]) / (STEPS[i][0] - STEPS[i - 1][0])) * (STEPS[i][1] - STEPS[i - 1][1]);
  return 1;
};

let current: Loader | null = null, timer = 0;
function play() {
  current?.el.remove(); window.clearInterval(timer);
  const l = current = new Loader();
  const t0 = performance.now();
  // updates arrive in irregular batches, as resources finish
  timer = window.setInterval(() => { const t = performance.now() - t0; l.progress(loaded(t)); if (t >= ms) { window.clearInterval(timer); void l.finish(); } }, 180);
}
document.getElementById("replay")?.addEventListener("click", play);
play();

// for frame sequences: stop everything at t ms after the start (the tube at what had loaded by then), or at t ms into the exit
(window as Window & { __preview?: unknown }).__preview = {
  seek(t: number) {
    window.clearInterval(timer);
    const el = current!.el; el.classList.remove("leaving");
    for (const a of el.getAnimations({ subtree: true })) { a.pause(); a.currentTime = t; }
    el.style.setProperty("--ld-p", loaded(t).toFixed(4));
  },
  exit(t: number) {
    window.clearInterval(timer);
    const el = current!.el;
    for (const a of el.getAnimations({ subtree: true })) { a.pause(); a.currentTime = 5000; }
    el.style.setProperty("--ld-p", "1");
    el.classList.add("leaving");
    for (const a of el.getAnimations()) if ((a as CSSAnimation).animationName === "ld-leave") { a.pause(); a.currentTime = t; }
  },
};
