// The carry profiler with real input: the whole chain, down and back up, in Chrome or Safari, driven by real macOS
// trackpad events (scripts/carry/swipe.swift) with nothing attached to the browser, so it behaves as it does for a
// visitor (Chrome prerenders only when no debugger is attached). Serves a COPY of dist/ with scripts/carry/instr.js
// injected into the four chain pages, collects what each page reports, and writes the run's log and a summary.
//   node scripts/carry/os.mjs --browser chrome|safari --out DIR [--record]
// Needs Accessibility permission for the terminal (to post input) and, with --record, Screen Recording.
// Safari: opens a window in the visitor's own Safari (it cannot be started apart), and closes it at the end.
import { spawn, execFileSync } from "node:child_process";
import { cpSync, mkdirSync, readFileSync, writeFileSync, existsSync, mkdtempSync, rmSync } from "node:fs";
import { join, dirname } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { serve } from "../serve_dist.mjs";

const here = dirname(fileURLToPath(import.meta.url)), web = join(here, "..", "..");
const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const browser = arg("--browser", "chrome"), out = arg("--out", join(tmpdir(), "carry-os")), record = process.argv.includes("--record");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
mkdirSync(out, { recursive: true });

// ---- the instrumented copy
const site = join(out, "site"); rmSync(site, { recursive: true, force: true });
cpSync(join(web, "dist"), site, { recursive: true });
cpSync(join(here, "instr.js"), join(site, "carry-instr.js"));
for (const f of ["index.html", "run.html", "docs.html", "sancho.html"]) {
  const p = join(site, f), s = readFileSync(p, "utf8");
  writeFileSync(p, s.replace("<head>", '<head>\n<script src="/carry-instr.js"></script>'));
}
// ---- the input tool
const swipeBin = join(out, "swipe");
if (!existsSync(swipeBin)) execFileSync("swiftc", ["-O", join(here, "swipe.swift"), "-o", swipeBin]);
if (execFileSync(swipeBin, ["--trusted"]).toString().trim() !== "true") throw new Error("this terminal may not post input: grant it Accessibility");

// ---- the server: every report kept, the latest per document
const docs = new Map();   // key: path + start
const port = 4600 + Math.floor(Math.random() * 300), base = `http://127.0.0.1:${port}`;
const srv = await serve(port, { root: site, carryLog: (b) => { try { const L = JSON.parse(b); docs.set(`${L.path}@${L.start}`, L); } catch { /* */ } } });
const latest = () => [...docs.values()].sort((a, b) => a.start - b.start).at(-1);

// ---- the browser, at a 1280x720 viewport
const W = 1280, H = 720;
let chrome = null, profile = null;
const osa = (...lines) => execFileSync("osascript", lines.flatMap((l) => ["-e", l])).toString().trim();
async function open(url) {
  if (browser === "chrome") {
    profile = mkdtempSync(join(tmpdir(), "carry-chrome-"));
    chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", [`--user-data-dir=${profile}`, "--no-first-run", "--no-default-browser-check",
      "--window-position=0,0", `--window-size=${W},${H + 87}`, url], { stdio: "ignore" });
  } else {
    osa('tell application "Safari" to make new document with properties {URL:"' + url + '"}', 'tell application "Safari" to set bounds of front window to {0, 30, ' + W + ", " + (30 + H + 80) + "}");
  }
}
function front() {
  if (browser === "chrome") osa(`tell application "System Events" to set frontmost of (first process whose unix id is ${chrome.pid}) to true`);
  else osa('tell application "Safari" to activate');
}
async function fitSafari() {   // make the viewport exactly 1280x720 once the page has said what it is
  if (browser !== "safari") return;
  const L = latest(); if (!L || L.vh === H) return;
  const b = osa('tell application "Safari" to get bounds of front window').split(", ").map(Number);
  osa(`tell application "Safari" to set bounds of front window to {${b[0]}, ${b[1]}, ${b[2]}, ${b[3] + (H - L.vh)}}`);
  await sleep(1500);
}
const center = () => { const L = latest(); return [Math.round(L.sx + L.vw / 2), Math.round(L.sy + L.vh / 2)]; };
const swipe = (dir, peak = 30, hold = 4, decay = 0.92) => { front(); const [x, y] = center(); execFileSync(swipeBin, [String(x), String(y), String(dir), String(peak), String(hold), String(decay)]); };
const key = (code) => { front(); execFileSync(swipeBin, ["key", String(code)]); };
const HOME = 115, END = 119;
async function until(f, ms) { const t = Date.now(); while (Date.now() - t < ms) { if (f()) return true; await sleep(100); } return false; }
const at = (path) => latest()?.path === path;

// ---- the route: down the chain, then back up
const steps = [];
let rec = null;
if (record) {
  rec = spawn("screencapture", ["-v", "-V", "120", "-x", join(out, "screen.mov")], { stdio: "ignore" });
}
await open(base + "/");
if (!(await until(() => at("/"), 15000))) throw new Error("no report from the home page");
await sleep(2500); await fitSafari(); await sleep(1500);
for (const to of ["/run.html", "/docs.html", "/sancho.html"]) {
  key(END); await sleep(2500);                         // at the end (the press that arrives never counts); the next page prepared meanwhile
  const t = Date.now(); swipe(+1);
  const ok = await until(() => at(to), 5000); await sleep(3500);
  steps.push({ to, dir: "down", carried: ok, wall_ms: Date.now() - t }); console.log("down", to, ok);
}
for (const to of ["/docs.html", "/run.html", "/"]) {
  if (to === "/docs.html") { key(END); await sleep(1500); }
  key(HOME); await sleep(2500);                        // back up to the top (passing near it prepares the previous page)
  const t = Date.now(); swipe(-1);
  const ok = await until(() => at(to), 5000); await sleep(3500);
  steps.push({ to, dir: "up", carried: ok, wall_ms: Date.now() - t }); console.log("up", to, ok);
}
await sleep(1500);
if (rec) { rec.kill("SIGINT"); await sleep(1500); }
writeFileSync(join(out, "log.json"), JSON.stringify([...docs.values()].sort((a, b) => a.start - b.start)));
writeFileSync(join(out, "steps.json"), JSON.stringify(steps, null, 1));
if (browser === "chrome") { chrome.kill("SIGTERM"); await sleep(1000); rmSync(profile, { recursive: true, force: true }); }
else osa('tell application "Safari" to close front window');
srv.close();
console.log("log:", join(out, "log.json"));
