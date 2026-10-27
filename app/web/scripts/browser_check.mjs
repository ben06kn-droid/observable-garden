// Drives the built site in headless Chrome under vercel.json's headers and reports what a visitor
// would hit: console errors, exceptions and content-security-policy violations (from the page and
// from the gate's worker), how long the gate takes, and screenshots of each stage.
//   node scripts/browser_check.mjs [--shots DIR] [--example nothing|planted|restart] [--chrome PATH]
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { serve } from "./serve_dist.mjs";

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const shots = arg("--shots", null);
const example = arg("--example", "nothing");
const chromePath = arg("--chrome", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome");
if (shots) mkdirSync(shots, { recursive: true });

const port = 4100 + Math.floor(Math.random() * 800);
const srv = await serve(port);
const base = `http://127.0.0.1:${port}`;
const profile = mkdtempSync(join(tmpdir(), "qx-check-"));
const headed = process.argv.includes("--headed");   // a real window, for the frame profile
// --uncapped: no vsync and no frame-rate limit, so a profile shows how many frames the page can make
// and what the worst one costs, even when the machine's display clock is throttled (a sleeping or
// locked display paces headless Chrome at 30 Hz)
const uncapped = process.argv.includes("--uncapped") ? ["--disable-frame-rate-limit", "--disable-gpu-vsync"] : [];
const chrome = spawn(chromePath, [...(headed ? ["--window-size=1366,868"] : ["--headless=new"]), ...uncapped, "--remote-debugging-port=0", `--user-data-dir=${profile}`, "--no-first-run", "--hide-scrollbars", "about:blank"],
                     { stdio: ["ignore", "ignore", "pipe"] });
const wsUrl = await new Promise((res, rej) => {
  let buf = "";
  chrome.stderr.on("data", (d) => { buf += d; const m = /DevTools listening on (ws:\/\/\S+)/.exec(buf); if (m) res(m[1]); });
  setTimeout(() => rej(new Error("Chrome did not start")), 15000);
});

const ws = new WebSocket(wsUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
let nextId = 1;
const waiting = new Map();
const issues = [];
const sessions = new Set();
const send = (method, params = {}, sessionId) => new Promise((res, rej) => {
  const id = nextId++;
  waiting.set(id, { res, rej });
  ws.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
});
const traceEvents = []; let traceDone = null;
const note = (where, kind, text) => issues.push({ where, kind, text: String(text).slice(0, 400) });
ws.addEventListener("message", async (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && waiting.has(m.id)) { const w = waiting.get(m.id); waiting.delete(m.id); m.error ? w.rej(new Error(m.error.message)) : w.res(m.result); return; }
  if (m.method === "Tracing.dataCollected") { traceEvents.push(...m.params.value); return; }
  if (m.method === "Tracing.tracingComplete") { traceDone?.(); return; }
  const where = m.sessionId ?? "browser";
  if (m.method === "Target.attachedToTarget") {
    const sid = m.params.sessionId; sessions.add(sid);
    await send("Runtime.enable", {}, sid).catch(() => {});
    await send("Log.enable", {}, sid).catch(() => {});
    await send("Runtime.runIfWaitingForDebugger", {}, sid).catch(() => {});
    await send("Target.setAutoAttach", { autoAttach: true, waitForDebuggerOnStart: false, flatten: true }, sid).catch(() => {});
  } else if (m.method === "Runtime.exceptionThrown") note(where, "exception", m.params.exceptionDetails?.exception?.description ?? m.params.exceptionDetails?.text);
  else if (m.method === "Runtime.consoleAPICalled" && ["error", "warning"].includes(m.params.type)) note(where, "console." + m.params.type, m.params.args.map((a) => a.value ?? a.description).join(" "));
  else if (m.method === "Log.entryAdded" && ["error", "warning"].includes(m.params.entry.level)) note(where, "log." + m.params.entry.source, m.params.entry.text);
});

const { targetId } = await send("Target.createTarget", { url: "about:blank" });
const { sessionId: page } = await send("Target.attachToTarget", { targetId, flatten: true });
for (const d of ["Runtime", "Log", "Page"]) await send(`${d}.enable`, {}, page);
await send("Target.setAutoAttach", { autoAttach: true, waitForDebuggerOnStart: false, flatten: true }, page);
const evaluate = async (expr) => (await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true }, page)).result.value;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function viewport(w, h) { await send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 600 }, page); }
async function go(path) {
  const loaded = new Promise((r) => { const f = (ev) => { const m = JSON.parse(ev.data); if (m.method === "Page.loadEventFired" && m.sessionId === page) { ws.removeEventListener("message", f); r(); } }; ws.addEventListener("message", f); });
  await send("Page.navigate", { url: base + path }, page);
  await loaded;
  await evaluate("document.fonts.ready.then(() => true)");
}
async function shot(name, full = false) {
  if (!shots) return;
  const p = { format: "png", captureBeyondViewport: full };
  if (full) { const hgt = await evaluate("document.documentElement.scrollHeight"); const w = await evaluate("innerWidth"); p.clip = { x: 0, y: 0, width: w, height: hgt, scale: 1 }; }
  const { data } = await send("Page.captureScreenshot", p, page);
  writeFileSync(join(shots, name + ".png"), Buffer.from(data, "base64"));
}
async function until(expr, ms) { const t0 = Date.now(); while (Date.now() - t0 < ms) { if (await evaluate(expr)) return Date.now() - t0; await sleep(100); } throw new Error("timed out waiting for " + expr); }

const report = { base, example, timings: {}, issues };
const probe = arg("--probe", null);   // evaluate one expression on the home page and stop
if (probe) {
  await viewport(1440, 900); await go("/");
  // --trace: record the probe like the performance panel and list where the time went, by event
  const tracing = process.argv.includes("--trace");
  if (tracing) await send("Tracing.start", { traceConfig: { includedCategories: ["devtools.timeline", "disabled-by-default-devtools.timeline", "blink", "cc", "viz", "gpu"], recordMode: "recordContinuously" } }, page);
  report.probe = await evaluate(probe);
  if (tracing) {
    const done = new Promise((r) => { traceDone = r; });
    await send("Tracing.end", {}, page); await done;
    const tot = new Map();
    for (const e of traceEvents) if (e.ph === "X" && e.dur) { const k = `${e.name} [tid ${e.tid}]`; tot.set(k, (tot.get(k) ?? 0) + e.dur / 1000); }
    report.probe = { result: report.probe, top: [...tot].sort((x, y) => y[1] - x[1]).slice(0, 30).map(([k, v]) => `${v.toFixed(0)} ms ${k}`) };
  }
  chrome.kill(); srv.close();
  console.log(JSON.stringify(report.probe, null, 1)); process.exit(0);
}
// The frame profile: what Chrome's performance panel records (devtools.timeline plus the frame
// category), over one transition, saved as a trace the panel can open. Frames are the compositor's
// DrawFrame events; the longest frame is the largest gap between two of them inside the window. A
// page-side rAF recorder and long-animation-frame entries run alongside as a cross-check.
const CATS = "devtools.timeline,disabled-by-default-devtools.timeline,disabled-by-default-devtools.timeline.frame,blink.user_timing,loading";
const RAF = `(() => { const d = [], loaf = []; let last = 0, on = true, po;
  try { po = new PerformanceObserver((l) => loaf.push(...l.getEntries().map((e) => e.duration))); po.observe({ type: "long-animation-frame" }); } catch {}
  const f = (t) => { if (last) d.push(t - last); last = t; if (on) requestAnimationFrame(f); }; requestAnimationFrame(f);
  window.__frames = { stop() { on = false; po?.disconnect(); return { raf_frames: d.length, raf_longest_ms: +Math.max(...d).toFixed(1), raf_over_20ms: d.filter((x) => x > 20).length, long_animation_frames: loaf.length }; } };
  return true; })()`;
async function frameProfile(name, act, ms) {
  traceEvents.length = 0;
  await send("Tracing.start", { traceConfig: { includedCategories: CATS.split(","), recordMode: "recordContinuously" } }, page);
  await evaluate(RAF);
  await sleep(300);
  const t0 = await evaluate(`performance.timeOrigin + performance.now()`);
  await act();
  await sleep(ms);
  const t1 = await evaluate(`performance.timeOrigin + performance.now()`);
  const raf = await evaluate(`window.__frames.stop()`);
  const done = new Promise((r) => { traceDone = r; });
  await send("Tracing.end", {}, page); await done;
  if (shots) writeFileSync(join(shots, `trace-${name}.json`), JSON.stringify({ traceEvents }));
  const draws = traceEvents.filter((e) => e.name === "DrawFrame").map((e) => e.ts / 1000).sort((a, b) => a - b);
  // the trace clock and the page clock differ; take the window as the last `span` of the trace's draws
  const span = t1 - t0, end = draws.length ? draws[draws.length - 1] : 0, inside = draws.filter((t) => t >= end - span);
  const gaps = inside.slice(1).map((t, i) => t - inside[i]);
  const main = (n) => traceEvents.filter((e) => e.name === n && e.ts / 1000 >= end - span).length;
  return { window_ms: Math.round(span), frames: inside.length, longest_frame_ms: gaps.length ? +Math.max(...gaps).toFixed(1) : null,
    frames_over_20ms: gaps.filter((g) => g > 20).length, layouts: main("Layout"), paints: main("Paint"), ...raf };
}
async function wheel(dy) { await send("Input.dispatchMouseEvent", { type: "mouseWheel", x: 400, y: 400, deltaX: 0, deltaY: dy }, page); }
try {
  for (const [vw, vh, tag] of [[1440, 900, "desktop"], [1366, 768, "laptop"]]) {
    await viewport(vw, vh);
    await go("/");
    await sleep(700);
    await shot(`${tag}-1-overview-top`);
    // page one scrolls freely by wheel to its last line; page two stays paper meanwhile
    const oneEnd = await evaluate(`document.getElementById('demo').offsetTop - innerHeight`);
    for (let left = oneEnd - 1; left > 0; left -= 100) { await wheel(Math.min(100, left)); await sleep(30); }
    await sleep(900);
    report[`${tag}_page_one_scrolls_freely`] = await evaluate(`Math.abs(scrollY - ${Math.max(0, oneEnd)}) < 4`);
    report[`${tag}_paper_until_snap`] = await evaluate(`document.body.dataset.page === 'one'`);
    await shot(`${tag}-2-overview-end`);
    // one more notch carries onto page two; paper until the carry arrives
    await wheel(100); await sleep(120);
    report[`${tag}_still_paper_mid_carry`] = await evaluate(`document.body.dataset.page === 'one' && document.getAnimations().some((a) => a.effect?.target?.tagName === 'MAIN')`);
    // reversing mid-carry is obeyed at once (the wheel is never trapped)
    await wheel(-100); await sleep(900);
    report[`${tag}_reverses_mid_carry`] = await evaluate(`Math.abs(scrollY - ${Math.max(0, oneEnd)}) < 4 && document.body.dataset.page === 'one'`);
    report[`${tag}_carry_profile`] = await frameProfile(`${tag}-carry`, async () => {
      await wheel(100); await sleep(60);
      report[`${tag}_carry_is`] = await evaluate(`document.getAnimations().filter((a) => a.effect?.target?.tagName === 'MAIN').map((a) => ({ props: [...new Set(a.effect.getKeyframes().flatMap((k) => Object.keys(k).filter((x) => !['offset', 'easing', 'composite', 'computedOffset'].includes(x))))], duration: a.effect.getTiming().duration, easing: a.effect.getTiming().easing }))`);
    }, 1300);
    await until(`document.body.dataset.page === 'two'`, 5000);
    await sleep(200);
    report[`${tag}_snapped`] = await evaluate(`Math.abs(scrollY - document.getElementById('demo').offsetTop) < 3`);
    // the leeway: a small nudge up stays on page two; a nudge, a pause and another goes back; so does
    // one gesture of 40% of the viewport
    const onTwo = `document.body.dataset.page === 'two' && Math.abs(scrollY - document.getElementById('demo').offsetTop) < 3`;
    const onOne = `document.body.dataset.page === 'one' && Math.abs(scrollY - ${Math.max(0, oneEnd)}) < 4`;
    await sleep(500); await wheel(-60); await sleep(60); await wheel(-60); await sleep(900);
    report[`${tag}_small_up_stays`] = await evaluate(onTwo);
    await wheel(-60); await sleep(1500);
    report[`${tag}_nudge_pause_nudge_leaves`] = await evaluate(onOne);
    await wheel(100); await until(`document.body.dataset.page === 'two'`, 5000); await sleep(800);
    for (let left = Math.ceil(vh * 0.42); left > 0; left -= 80) { await wheel(-Math.min(80, left)); await sleep(30); }
    await sleep(1500);
    report[`${tag}_big_gesture_leaves`] = await evaluate(onOne);
    await wheel(100); await until(`document.body.dataset.page === 'two'`, 5000); await sleep(800);
    await sleep(500);
    await shot(`${tag}-3-demo-ready`);
  }
  await viewport(1440, 900);
  await go("/");
  await evaluate(`window.scrollTo(0, document.getElementById('demo').offsetTop)`); await sleep(500);
  const idx = { nothing: 0, planted: 1, restart: 2 }[example];
  await until(`document.querySelectorAll('#chips .chip').length >= 3`, 10000);
  await evaluate(`document.querySelectorAll('#chips .chip')[${idx}].click(); document.getElementById('run').click(); true`);
  const t0 = Date.now();
  report.timings.gate_loaded_and_search_started_ms = await until(`document.getElementById('phase').textContent === 'The search'`, 120000);
  await sleep(1500); await shot("4-demo-search");
  report.search = await evaluate(`({ tree_stems: document.querySelectorAll('#garden .stem').length, bed_growing: document.querySelectorAll('#bed .flowers .bf:not([transform*="scale(0.000)"])').length })`);
  await until(`document.getElementById('phase').textContent === 'The null'`, 120000); await sleep(1200); await shot("5-demo-null");
  await until(`document.getElementById('phase').textContent === 'The verdict'`, 180000);
  report.timings.click_to_verdict_ms = Date.now() - t0;
  await sleep(1600); await shot("6-demo-verdict");
  report.verdict = await evaluate(`({ word: document.getElementById('big').textContent, line: document.getElementById('line').textContent, card: document.querySelector('#verdict .word')?.textContent,
    blossoms_open: document.querySelectorAll('#garden .blossom.open').length, blossoms: document.querySelectorAll('#garden .blossom').length,
    bed_flowers: document.querySelectorAll('#bed .flowers .bf').length, bed_open: document.querySelectorAll('#bed .flowers .bloom.open').length, enter_shown: !document.getElementById('enter').hidden })`);
  // into the run: the run enlarges and the view goes blue; out with Esc (via history), then Back
  report.zoom_profile = await frameProfile("zoom", async () => { await evaluate(`document.getElementById('enter').click(); true`); }, 1400);
  report.zoom_is = await evaluate(`document.getAnimations().filter((a) => !(a instanceof CSSAnimation) && a.effect?.target?.closest?.('#inside')).map((a) => ({ on: a.effect.target.className, props: [...new Set(a.effect.getKeyframes().flatMap((k) => Object.keys(k).filter((x) => !['offset', 'easing', 'composite', 'computedOffset'].includes(x))))], duration: a.effect.getTiming().duration, easing: a.effect.getTiming().easing }))`);
  await shot("7-inside-run");
  report.inside = await evaluate(`({ open: document.getElementById('inside').classList.contains('open'), title: document.getElementById('run-title')?.textContent,
    moves: document.querySelectorAll('#inside li').length, focus_in: document.activeElement?.id === 'run-title', hash: location.hash,
    petals_pink: getComputedStyle(document.querySelector('#inside .petal path')).fill })`);
  await evaluate(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })); true`);
  await until(`document.getElementById('inside').hidden`, 5000); await sleep(200);
  report.inside.closed_by_esc = await evaluate(`document.body.dataset.page === 'two' && location.hash === ''`);
  await evaluate(`document.getElementById('bed').dispatchEvent(new MouseEvent('click', { bubbles: true })); true`);
  await until(`!document.getElementById('inside').hidden`, 5000); await sleep(800);
  await evaluate(`history.back(); true`);
  await until(`document.getElementById('inside').hidden`, 5000);
  report.inside.closed_by_back = true;
  await evaluate(`window.scrollTo(0, document.getElementById('record').offsetTop); true`); await sleep(400); await shot("8-record");
  await go(`/result.html?ex=${example}`);
  await until(`!!document.querySelector('#verdict:not(.idle)')`, 180000); await sleep(1600);
  await shot("9-result", true);
  for (const p of ["/docs.html", "/privacy.html", "/terms.html", "/run.html", "/viewer.html", "/nope.html"]) { await go(p); }
  report.paper_link = await evaluate(`[...document.querySelectorAll('a')].filter(a => a.textContent === 'Paper').every(a => a.href.startsWith('https://papers.ssrn.com/') && a.target === '_blank' && a.rel.includes('noopener') && a.rel.includes('noreferrer'))`);
  await go("/docs.html"); await shot("10-docs");
  await viewport(390, 844); await go("/"); await shot("11-phone-overview");
  await evaluate(`window.scrollTo(0, document.getElementById('demo').offsetTop)`); await sleep(900); await shot("12-phone-demo");
  report.phone_overflow = await evaluate(`document.documentElement.scrollWidth > innerWidth`);
} catch (e) {
  report.error = String(e.message ?? e);
} finally {
  const exited = new Promise((r) => chrome.once("exit", r));
  chrome.kill(); srv.close();
  await Promise.race([exited, sleep(5000)]);
  try { rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 }); } catch { /* a temporary profile; the OS will clear it */ }
}
report.csp_violations = issues.filter((i) => /Content Security Policy|Refused to/i.test(i.text)).length;
console.log(JSON.stringify(report, null, 1));
process.exit(report.error || report.csp_violations || issues.some((i) => i.kind === "exception") ? 1 : 0);
