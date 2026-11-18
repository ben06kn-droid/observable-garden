// Catches long frames on the one page while it scrolls back and forth across the run/docs boundary, with a Chrome
// trace of each: what ran on the page's main thread, the compositor, the GPU process and the gate's worker during
// that frame. Headed Chrome (the GPU as a visitor has it), a debugger attached (harmless now there is no
// prerendering), wheel input through DevTools.
//   node scripts/freeze_trace.mjs --out DIR [--root DIST] [--seconds 30] [--path /] [--focus]
// --focus: focus the run form's prompt as soon as the site is shown (the visitor who starts Pyodide at once)
import { spawn } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { serve } from "./serve_dist.mjs";

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const out = arg("--out"), root = arg("--root", join(import.meta.dirname, "..", "dist")), seconds = +arg("--seconds", "30");
mkdirSync(out, { recursive: true });
const port = 5900 + Math.floor(Math.random() * 90);
const srv = await serve(port, { root });
const profile = mkdtempSync(join(tmpdir(), "qx-freeze-"));
const chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", ["--remote-debugging-port=0", `--user-data-dir=${profile}`, "--no-first-run", "--no-default-browser-check", "--window-position=0,0", "--window-size=1280,807", "about:blank"], { stdio: "ignore" });
let wsUrl;
for (let i = 0; i < 100 && !wsUrl; i++) { try { const p = readFileSync(join(profile, "DevToolsActivePort"), "utf8").split("\n")[0]; wsUrl = (await (await fetch(`http://127.0.0.1:${p}/json/list`)).json()).find((t) => t.type === "page")?.webSocketDebuggerUrl; } catch { await sleep(100); } }
const ws = new WebSocket(wsUrl); await new Promise((r) => ws.addEventListener("open", r, { once: true }));
let id = 0; const pend = new Map(), events = []; let traceDone = null, stream = null;
ws.addEventListener("message", (e) => { const m = JSON.parse(e.data);
  if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
  if (m.method === "Tracing.tracingComplete") { stream = m.params.stream; traceDone?.(); } });
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async (expression) => (await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true })).result?.result?.value;

// every frame's start (epoch ms), and marks for the gate's steps
await send("Page.enable");
await send("Page.addScriptToEvaluateOnNewDocument", { source: `(() => { window.__f = []; const f = (t) => { window.__f.push(performance.timeOrigin + t); requestAnimationFrame(f); }; requestAnimationFrame(f); })();` });
await send("Tracing.start", { transferMode: "ReturnAsStream", traceConfig: { recordMode: "recordContinuouslyUntilFull", includedCategories: [
  "devtools.timeline", "disabled-by-default-devtools.timeline", "disabled-by-default-devtools.timeline.frame", "blink.user_timing", "v8.execute", "v8", "toplevel", "gpu", "viz", "cc", "blink.console", "loading", "v8.wasm", "disabled-by-default-v8.gc"] } });
await send("Page.navigate", { url: `http://127.0.0.1:${port}${arg("--path", "/")}` });
for (let i = 0; i < 200; i++) { if (await evaluate(`performance.getEntriesByName("qx-revealed").length > 0`)) break; await sleep(100); }
const t0 = await evaluate("performance.timeOrigin + performance.now()");
if (process.argv.includes("--focus")) await evaluate(`document.getElementById("f-prompt").focus({ preventScroll: true }), true`);
// to the run/docs boundary, then back and forth across it
const bound = await evaluate(`(() => { const s = document.querySelector('[data-section="docs"]'); return Math.round(s.getBoundingClientRect().top + scrollY); })()`);
await evaluate(`scrollTo(0, ${bound} - innerHeight * 1.2), true`); await sleep(500);
const wheel = async (dy) => { for (let k = 0; k < 12; k++) { await send("Input.dispatchMouseEvent", { type: "mouseWheel", x: +arg("--x", "640"), y: 400, deltaX: 0, deltaY: dy }); await sleep(16); } };
const end = Date.now() + seconds * 1000; let dir = 1;
while (Date.now() < end) { await wheel(dir * 100); await sleep(300); dir = -dir; }
const frames = JSON.parse(await evaluate("JSON.stringify(window.__f ?? [])"));
const marks = await evaluate(`performance.getEntriesByType("mark").map((m) => [m.name, Math.round(performance.timeOrigin + m.startTime)])`);
traceDone = null; const done = new Promise((r) => { traceDone = r; });
await send("Tracing.end"); await done;
let data = "";
for (;;) { const r = (await send("IO.read", { handle: stream, size: 1 << 22 })).result; data += r.base64Encoded ? Buffer.from(r.data, "base64").toString() : r.data; if (r.eof) break; }
writeFileSync(join(out, "trace.json"), data);
const trace = JSON.parse(data); const ev = trace.traceEvents ?? trace;
// thread names, and the trace clock against epoch (a mark both have: qx-revealed)
const names = new Map(); for (const e of ev) if (e.ph === "M" && e.name === "thread_name") names.set(`${e.pid}:${e.tid}`, e.args.name);
const um = ev.find((e) => e.name === "qx-revealed" && e.ph !== "M"), rev = marks.find(([n]) => n === "qx-revealed")[1];
const toEpoch = (ts) => rev + (ts - um.ts) / 1000;
// the long frames after the reveal, and what was over 15 ms during each, by thread
const long = [];
for (let i = 1; i < frames.length; i++) { const d = frames[i] - frames[i - 1]; if (frames[i] > t0 && d > 60) long.push([frames[i - 1], d]); }
const report = { revealed_at: rev, marks: marks.map(([n, t]) => [n, t - rev]), frames: frames.filter((t) => t > t0).length, long_frames: [] };
for (const [s, d] of long) {
  const busy = ev.filter((e) => e.ph === "X" && e.dur > 15000 && toEpoch(e.ts) < s + d && toEpoch(e.ts) + e.dur / 1000 > s)
    .map((e) => [names.get(`${e.pid}:${e.tid}`) ?? `${e.pid}:${e.tid}`, e.name, Math.round(e.dur / 1000), Math.round(toEpoch(e.ts) - s), JSON.stringify(e.args?.data ?? e.args ?? {}).slice(0, 160)]);
  report.long_frames.push({ at_ms_after_reveal: Math.round(s - rev), frame_ms: Math.round(d), busy });
}
writeFileSync(join(out, "report.json"), JSON.stringify(report, null, 1));
console.log(JSON.stringify({ frames: report.frames, long: report.long_frames.map((l) => [l.at_ms_after_reveal, l.frame_ms]), marks: report.marks }));
ws.close(); chrome.kill(); srv.close(); setTimeout(() => rmSync(profile, { recursive: true, force: true }), 1000);
