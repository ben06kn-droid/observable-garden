// Summarises a carry profiler run (scripts/carry/os.mjs's log.json): one line per carry.
//   node scripts/carry/report.mjs DIR
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const dir = process.argv[2];
const mark = (d, p) => d.marks.find(([, n]) => n.startsWith(p))?.[0];
// in the order the pages were shown: a prerendered page started long before it was activated
const shown = (d) => mark(d, "activated") ?? d.start;
const docs = JSON.parse(readFileSync(join(dir, "log.json"), "utf8")).filter((d) => !d.marks.some(([, n]) => n.includes("prerendering")) || mark(d, "activated")).sort((a, b) => shown(a) - shown(b));
const gaps = (fr, a, b) => { const s = fr.filter((t) => t >= a && t <= b), g = s.slice(1).map((t, i) => t - s[i]); return { frames: s.length, longest: Math.round(Math.max(0, ...g) * 10) / 10, over20: g.filter((x) => x > 20).length, over34: g.filter((x) => x > 34).length }; };
const rows = [];
console.log(`pages in order: ${docs.map((d) => d.path).join(" → ")}`);
for (let i = 1; i < docs.length; i++) {
  const from = docs[i - 1], to = docs[i];
  if (!to.carry) continue;
  const trig = from.trigger, swap = mark(from, "pageswap"), ready = mark(to, "vt-ready"), fin = mark(to, "vt-finished"), reveal = mark(to, "pagereveal");
  const down = to.carry.dir === "down";
  // the push: wheel events at the edge before the trigger, in the last gesture
  const atEdge = from.wheel.filter(([t, dy, y, m]) => t <= trig && (down ? dy > 0 && y >= m - 2 : dy < 0 && y <= 2));
  const lastGap = atEdge.findLastIndex((e, k) => k > 0 && e[0] - atEdge[k - 1][0] > 100);
  const push = atEdge.slice(Math.max(0, lastGap)).reduce((s, e) => s + Math.abs(e[1]), 0);
  const pushStart = atEdge[Math.max(0, lastGap)]?.[0] ?? trig;
  const gl = to.marks.filter(([, n]) => /^getContext|^worker/.test(n)).map(([t, n]) => `${n.split(" ").slice(0, 3).join(" ")} @${Math.round(t - (fin ?? reveal))}`);
  // the landing: did the page move before the driver's next key? (down lands at 0, up at the end)
  const settle = (fin ?? reveal) + 1500, ys = to.scroll.filter(([t]) => t >= reveal && t <= settle).map(([, y]) => y);
  const r = {
    carry: `${from.path} → ${to.path} (${to.carry.dir})`,
    prerendered: !!to.activationStart, view_transition: to.carry.viewTransition,
    push_px_at_edge: push, push_ms: Math.round(trig - pushStart),
    trigger_to_motion_ms: ready ? Math.round(ready - trig) : null, trigger_to_pageswap_ms: swap ? Math.round(swap - trig) : null,
    transition_ms: ready && fin ? Math.round(fin - ready) : null,
    push_frames: gaps(from.frames, pushStart, trig),
    transition_frames: ready && fin ? gaps(to.frames, ready, fin) : null,
    landing: { swallowed: to.carry.landing, scroll_moved_px: ys.length ? Math.max(...ys) - Math.min(...ys) : 0 },
    started_after_transition: gl,
  };
  rows.push(r);
  console.log(JSON.stringify(r));
}
writeFileSync(join(dir, "report.json"), JSON.stringify({ pages: docs.map((d) => d.path), viewport: `${docs[0]?.vw}x${docs[0]?.vh}`, ua: docs[0]?.ua, carries: rows }, null, 1));
