// Measures the one-page site in Chrome or Safari on this machine, with real macOS input and nothing attached to the
// browser (scripts/carry/swipe.swift posts trackpad swipes; scripts/carry/instr.js, injected into a COPY of the build,
// reports each page's frames, scroll and marks to this script's server):
//   - time behind the loading screen: a first visit in the session, then a later one (the finished B, no minimum);
//   - frame times while scrolling across a boundary between sections, down and back up, twice each way;
//   - memory: the browser's own processes (macOS footprint), 10 s after the site is shown and after a pass through
//     every section, for the one page and, with --baseline DIST, for each page of a multi-page build on its own.
//   node scripts/onepage_measure.mjs --browser chrome|safari --out DIR [--root DIST] [--baseline DIST]
// Needs Accessibility permission for the terminal (to post input). Safari: windows in the visitor's own Safari.
import { spawn, execFileSync } from "node:child_process";
import { cpSync, mkdirSync, readFileSync, writeFileSync, existsSync, mkdtempSync, rmSync } from "node:fs";
import { join, dirname } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { serve } from "./serve_dist.mjs";

const here = dirname(fileURLToPath(import.meta.url)), web = join(here, "..");
const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const browser = arg("--browser", "chrome"), out = arg("--out", join(tmpdir(), "onepage-measure"));
const root = arg("--root", join(web, "dist")), baseline = arg("--baseline", null);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
mkdirSync(out, { recursive: true });
const osa = (...lines) => execFileSync("osascript", lines.flatMap((l) => ["-e", l])).toString().trim();

// ---- an instrumented copy of a build
function instrumented(src, name) {
  const site = join(out, name); rmSync(site, { recursive: true, force: true });
  cpSync(src, site, { recursive: true });
  cpSync(join(here, "carry", "instr.js"), join(site, "carry-instr.js"));
  for (const f of ["index.html", "run.html", "docs.html", "sancho.html"]) { const p = join(site, f); writeFileSync(p, readFileSync(p, "utf8").replace("<head>", '<head>\n<script src="/carry-instr.js"></script>')); }
  return site;
}
const swipeBin = join(out, "swipe");
if (!existsSync(swipeBin)) execFileSync("swiftc", ["-O", join(here, "carry", "swipe.swift"), "-o", swipeBin]);

// ---- reports from the pages: the latest per document
let docs = new Map();
const latest = () => [...docs.values()].sort((a, b) => a.start - b.start).at(-1);
const pmark = (L, n) => L?.pmarks?.find(([m]) => m === n)?.[1];
async function until(f, ms) { const t = Date.now(); while (Date.now() - t < ms) { if (f()) return true; await sleep(100); } return false; }

// ---- the browser
const W = 1280, H = 720;
let chrome = null, profile = null;
function openChrome(url) {
  profile = mkdtempSync(join(tmpdir(), "onepage-chrome-"));
  chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", [`--user-data-dir=${profile}`, "--no-first-run", "--no-default-browser-check", "--window-position=0,0", `--window-size=${W},${H + 87}`, url], { stdio: "ignore" });
}
function closeChrome() { chrome?.kill("SIGTERM"); chrome = null; const p = profile; setTimeout(() => rmSync(p, { recursive: true, force: true }), 1500); }
const navigate = (url) => browser === "chrome" ? execFileSync("osascript", ["-e", `tell application "System Events" to set frontmost of (first process whose unix id is ${chrome.pid}) to true`]) && osaKeyUrl(url) : osa(`tell application "Safari" to set URL of front document to "${url}"`);
function osaKeyUrl(url) {   // Chrome without a debugger: type the address (Cmd-L, the URL, Return)
  osa('tell application "System Events" to keystroke "l" using command down'); execFileSync("sleep", ["0.2"]);
  osa(`tell application "System Events" to keystroke "${url}"`); osa('tell application "System Events" to key code 36');
}
function front() { if (browser === "chrome") osa(`tell application "System Events" to set frontmost of (first process whose unix id is ${chrome.pid}) to true`); else { osa('tell application "System Events" to set frontmost of process "Safari" to true'); execFileSync("sleep", ["0.3"]); } }   // ("activate" can leave another app in front; the swipes would go to it)
async function fitSafari() {
  if (browser !== "safari") return; const L = latest(); if (!L || L.vh === H) return;
  const b = osa('tell application "Safari" to get bounds of front window').split(", ").map(Number);
  osa(`tell application "Safari" to set bounds of front window to {${b[0]}, ${b[1]}, ${b[2]}, ${b[3] + (H - L.vh)}}`); await sleep(1200);
}
const center = () => { const L = latest(); return [Math.round(L.sx + L.vw / 2), Math.round(L.sy + L.vh / 2)]; };
const swipe = (dir, peak = 30, hold = 4, decay = 0.92) => { front(); const [x, y] = center(); execFileSync(swipeBin, [String(x), String(y), String(dir), String(peak), String(hold), String(decay)]); };

// ---- memory: the browser's processes for this page (macOS footprint, MB)
function footprintMB(pid) {
  try { const m = execFileSync("footprint", [String(pid)], { stderr: "ignore" }).toString().match(/phys_footprint:\s*([\d.]+)\s*(KB|MB|GB)/); return m ? +(m[1] * (m[2] === "GB" ? 1024 : m[2] === "KB" ? 1 / 1024 : 1)).toFixed(1) : null; } catch { return null; }
}
const ps = () => execFileSync("ps", ["-A", "-o", "pid=,command="]).toString().split("\n").map((l) => l.trim()).filter(Boolean).map((l) => { const i = l.indexOf(" "); return { pid: +l.slice(0, i), cmd: l.slice(i + 1) }; });
function chromeProcs() {
  const mine = ps().filter((p) => p.cmd.includes(profile));
  const renderers = mine.filter((p) => p.cmd.includes("--type=renderer") && !p.cmd.includes("--extension-process")).map((p) => ({ pid: p.pid, mb: footprintMB(p.pid) })).sort((a, b) => b.mb - a.mb);
  const gpu = mine.find((p) => p.cmd.includes("--type=gpu-process"));
  return { renderer_mb: renderers[0]?.mb ?? null, gpu_mb: gpu ? footprintMB(gpu.pid) : null };
}
const webContent = () => new Set(ps().filter((p) => p.cmd.includes("com.apple.WebKit.WebContent")).map((p) => p.pid));
const safariGpu = () => ps().find((p) => p.cmd.includes("com.apple.WebKit.GPU"))?.pid;

// ---- one page load: open, wait until shown, a pass through every section, 10 s, memory
async function visit(site, path, { first = true } = {}) {
  docs = new Map();
  const port = 4900 + Math.floor(Math.random() * 300), base = `http://127.0.0.1:${port}`;
  const srv = await serve(port, { root: site, carryLog: (b) => { try { const L = JSON.parse(b); docs.set(`${L.path}@${L.start}`, L); } catch { /* */ } } });
  let before = null, gpu0 = null;
  if (browser === "chrome") openChrome(base + path);
  else { before = new Map([...webContent()].map((pid) => [pid, footprintMB(pid)])); gpu0 = footprintMB(safariGpu()); osa(`tell application "Safari" to make new document with properties {URL:"${base + path}"}`, `tell application "Safari" to set bounds of front window to {0, 30, ${W}, ${30 + H + 80}}`); }
  const shown = await until(() => { const L = latest(); return L && (pmark(L, "qx-revealed") || !L.sections?.length); }, 30000);
  await fitSafari();
  return { srv, base, before, gpu0, shown };
}
async function memoryAfter(v, sections) {
  // a pass through every section (each scene draws at least once), back to the start, then 10 s
  if (sections) for (const k of [1, 2, 3, 4, 5, 6]) { swipe(+1, 60, 8, 0.94); await sleep(400); }
  if (sections) for (const k of [1, 2, 3, 4, 5, 6]) { swipe(-1, 60, 8, 0.94); await sleep(400); }
  await sleep(10000);
  if (browser === "chrome") return chromeProcs();
  // the page's Web Content process: the one that grew most since before it opened (Safari often puts a page in a
  // process it started earlier, so "the new one" is not reliable)
  const now = [...webContent()].map((pid) => ({ pid, mb: footprintMB(pid), was: v.before.get(pid) ?? 0 })).sort((a, b) => (b.mb - b.was) - (a.mb - a.was));
  return { webcontent_mb: now[0]?.mb ?? null, gpu_delta_mb: +(footprintMB(safariGpu()) - v.gpu0).toFixed(1) };
}
async function leave(v) { if (browser === "chrome") closeChrome(); else osa('tell application "Safari" to close front window'); v.srv.close(); await sleep(2500); }

const stat = (g) => { if (!g.length) return null; const s = [...g].sort((a, b) => a - b); return { frames: g.length, median_ms: +s[Math.floor(s.length / 2)].toFixed(1), p95_ms: +s[Math.floor(s.length * 0.95)].toFixed(1), longest_ms: +s.at(-1).toFixed(1), over_20ms: g.filter((x) => x > 20).length, over_34ms: g.filter((x) => x > 34).length }; };
/** frame gaps while scrolling (from t0), and those while each boundary is on screen (the next section's top inside the viewport) */
function frameStats(Q, t0) {
  const yAt = (t) => { let y = 0; for (const [ts, yy] of Q.scroll) { if (ts > t) break; y = yy; } return y; };
  const fr = Q.frames.filter((t) => t > t0), all = [], per = {};
  const bounds = (Q.sections ?? []).slice(1);
  for (let i = 1; i < fr.length; i++) {
    const g = fr[i] - fr[i - 1], y = yAt(fr[i]); all.push(g);
    for (const [n, top] of bounds) if (y > top - Q.vh && y < top) (per[n] ??= []).push(g);
  }
  return { all_scrolling: stat(all), ...Object.fromEntries(Object.entries(per).map(([n, g]) => [`boundary_into_${n}`, stat(g)])) };
}
async function scrollThrough(down = 14, up = 14) {
  for (let i = 0; i < down; i++) { swipe(+1, 45, 6, 0.93); await sleep(150); }
  await sleep(800);
  for (let i = 0; i < up; i++) { swipe(-1, 45, 6, 0.93); await sleep(150); }
  await sleep(1500);
}
const result = { browser, viewport: `${W}x${H}`, when: new Date().toISOString() };
const one = instrumented(root, "site-onepage");

// 1. time behind the loading screen, a first visit and then a later one in the session; frames across the boundary
{
  const v = await visit(one, "/");
  const L = latest();
  result.first_visit = { work_done_ms: Math.round(pmark(L, "qx-work-done") - L.start), revealed_ms: Math.round(pmark(L, "qx-revealed") - L.start) };
  await sleep(3000);
  // frames: one scroll down through all four sections and back up, real trackpad swipes
  const t0 = Date.now(); await scrollThrough();
  const Q = latest();
  const ys = Q.scroll.filter(([t]) => t > t0).map(([, y]) => y);
  result.scrolling = { scrolled_px: ys.length ? [Math.min(...ys), Math.max(...ys)] : null, sections: Q.sections, ...frameStats(Q, t0), long_main_thread_frames: (Q.loaf ?? []).filter(([t]) => t > t0).map(([, d, bl, sc, y]) => ({ ms: d, blocking: bl, at_scroll: y, scripts: sc })) };
  // a later visit in the session: the address of the run section, typed
  docs = new Map(); navigate(v.base + "/run.html");
  await until(() => { const R = latest(); return R && R.path === "/run.html" && pmark(R, "qx-revealed"); }, 20000);
  const R = latest();
  result.later_visit = { path: R.path, work_done_ms: Math.round(pmark(R, "qx-work-done") - R.start), revealed_ms: Math.round(pmark(R, "qx-revealed") - R.start), at_run: Math.abs((R.scroll.at(-1)?.[1] ?? 0) - R.sections.find(([n]) => n === "run")[1]) < 3 };
  await leave(v);
}
// 2. memory: the one page, then each page of the multi-page build on its own
if (!process.argv.includes("--no-memory")) {
  const v = await visit(one, "/"); result.memory = { onepage: await memoryAfter(v, true) }; await leave(v);
  if (baseline) {
    const mp = instrumented(baseline, "site-multipage");
    result.baseline_scrolling = {};
    for (const p of ["/", "/run.html", "/docs.html", "/sancho.html"]) {
      const w = await visit(mp, p); await sleep(3000);
      const t0 = Date.now(); await scrollThrough(8, 8); result.baseline_scrolling[p] = frameStats(latest(), t0).all_scrolling;
      result.memory[`multipage ${p}`] = await memoryAfter(w, false); await leave(w);
    }
  }
}
writeFileSync(join(out, `result-${browser}.json`), JSON.stringify(result, null, 1));
console.log(JSON.stringify(result, null, 1));
