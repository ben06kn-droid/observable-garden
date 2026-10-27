// Drives the built site in headless Chrome under vercel.json's headers and reports what a visitor
// would hit: console errors, exceptions and content-security-policy violations (from the page and
// from the gate's worker), how long the gate takes, and screenshots of each stage.
//   node scripts/browser_check.mjs [--shots DIR] [--example nothing|planted|restart] [--chrome PATH]
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { inflateSync } from "node:zlib";
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
// on CI only: a downloaded Chrome on Ubuntu 24.04 runners cannot start its sandbox (AppArmor), and the
// one page it loads is this site's own build
const ci = process.env.CI ? ["--no-sandbox"] : [];
const chrome = spawn(chromePath, [...(headed ? ["--window-size=1366,868"] : ["--headless=new"]), ...uncapped, ...ci, "--remote-debugging-port=0", `--user-data-dir=${profile}`, "--no-first-run", "--hide-scrollbars", "about:blank"],
                     { stdio: ["ignore", "ignore", "pipe"] });
// Readiness: Chrome writes its debugging port to DevToolsActivePort in the profile once it listens;
// poll for that file, then for /json/version answering, for up to 60 s (a cold CI runner can take well
// over the 15 s this used to allow). If Chrome exits first, fail at once with what it printed.
let chromeErr = "", chromeExited = null;
chrome.stderr.on("data", (d) => { chromeErr = (chromeErr + d).slice(-4000); });
chrome.once("exit", (code, signal) => { chromeExited = { code, signal }; });
chrome.once("error", (e) => { chromeExited = { error: e.message }; });   // not found, not executable
async function chromeReady(ms = 60000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    if (chromeExited) throw new Error(`Chrome exited before it was ready (${JSON.stringify(chromeExited)}): ${chromeErr.trim().split("\n").slice(-5).join(" | ")}`);
    try {
      const p = readFileSync(join(profile, "DevToolsActivePort"), "utf8").trim().split("\n")[0];
      const v = await (await fetch(`http://127.0.0.1:${p}/json/version`)).json();
      if (v.webSocketDebuggerUrl) return v.webSocketDebuggerUrl;
    } catch { /* not yet */ }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`Chrome did not become ready within ${ms / 1000} s: ${chromeErr.trim().split("\n").slice(-5).join(" | ")}`);
}
const wsUrl = await chromeReady();

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
// ---- contrast against the actual scene: hide the text, screenshot what is behind it (several frames,
// petals falling), and compare the text's colour with every pixel behind each element (WCAG 2 ratio)
function decodePng(buf) {
  let p = 8, w = 0, h = 0, type = 0; const idat = [];
  while (p < buf.length) {
    const len = buf.readUInt32BE(p), kind = buf.toString("ascii", p + 4, p + 8), d = buf.subarray(p + 8, p + 8 + len);
    if (kind === "IHDR") { w = d.readUInt32BE(0); h = d.readUInt32BE(4); type = d[9]; }
    else if (kind === "IDAT") idat.push(d);
    p += 12 + len;
  }
  const bpp = type === 6 ? 4 : 3, raw = inflateSync(Buffer.concat(idat)), stride = w * bpp, out = Buffer.alloc(h * stride);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (stride + 1)], row = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1));
    for (let x = 0; x < stride; x++) {
      const a = x >= bpp ? out[y * stride + x - bpp] : 0, b = y ? out[(y - 1) * stride + x] : 0, c = x >= bpp && y ? out[(y - 1) * stride + x - bpp] : 0;
      const pa = Math.abs(b - c), pb = Math.abs(a - c), pc = Math.abs(a + b - 2 * c);
      const pred = f === 0 ? 0 : f === 1 ? a : f === 2 ? b : f === 3 ? (a + b) >> 1 : pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
      out[y * stride + x] = (row[x] + pred) & 255;
    }
  }
  return { w, h, bpp, px: out };
}
const lin = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
const lum = (r, g, b) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
async function contrast(selector, samples = 6) {
  const els = await evaluate(`[...document.querySelectorAll(${JSON.stringify(selector)})].filter((e) => e.offsetParent !== null && e.textContent.trim()).map((e, i) => {
    e.dataset.measure = i; const r = e.getBoundingClientRect(), c = getComputedStyle(e).color.match(/[0-9.]+/g).map(Number);
    return { i, name: (e.id || e.className || e.tagName) + ': ' + e.textContent.trim().slice(0, 24), x: r.left, y: r.top, w: r.width, h: r.height, c };
  })`);
  const worst = els.map(() => Infinity), lows = els.map(() => []);
  for (let k = 0; k < samples; k++) {
    // the text hidden, and its own underline or marker too, so only the scene behind it is measured
    await evaluate(`document.querySelectorAll('[data-measure]').forEach((e) => { for (const [k, v] of [['color', 'transparent'], ['text-shadow', 'none'], ['border-color', 'transparent'], ['box-shadow', 'none']]) e.style.setProperty(k, v, 'important'); }); true`);
    await sleep(60);
    const { data } = await send("Page.captureScreenshot", { format: "png" }, page);
    await evaluate(`document.querySelectorAll('[data-measure]').forEach((e) => { for (const k of ['color', 'text-shadow', 'border-color', 'box-shadow']) e.style.removeProperty(k); }); true`);
    const img = decodePng(Buffer.from(data, "base64"));
    els.forEach((e, n) => {
      const L = lum(e.c[0], e.c[1], e.c[2]);
      for (let y = Math.max(0, Math.floor(e.y)); y < Math.min(img.h, Math.ceil(e.y + e.h)); y++)
        for (let x = Math.max(0, Math.floor(e.x)); x < Math.min(img.w, Math.ceil(e.x + e.w)); x++) {
          const o = (y * img.w + x) * img.bpp, Lb = lum(img.px[o], img.px[o + 1], img.px[o + 2]);
          const r = (Math.max(L, Lb) + 0.05) / (Math.min(L, Lb) + 0.05);
          if (r < worst[n]) worst[n] = r;
          if (r < 4.5) lows[n].push(r);
        }
    });
    await sleep(450);
  }
  await evaluate(`document.querySelectorAll('[data-measure]').forEach((e) => e.removeAttribute('data-measure')); true`);
  return els.map((e, n) => ({ el: e.name, worst: +worst[n].toFixed(2), px_below_4_5: lows[n].length }));
}

async function wheel(dy) { await send("Input.dispatchMouseEvent", { type: "mouseWheel", x: 400, y: 400, deltaX: 0, deltaY: dy }, page); }
try {
  for (const [vw, vh, tag] of [[1440, 900, "desktop"], [1366, 768, "laptop"]]) {
    await viewport(vw, vh);
    await go("/");
    await sleep(700);
    await shot(`${tag}-1-overview-top`);
    if (tag === "desktop") report.shake_page_one = await evaluate(`(() => { const g = [...document.querySelectorAll('#bg-trees .real .stem')].find((e) => { const r = e.getBoundingClientRect(); return r.left > 800 && r.top < innerHeight; });
      if (!g) return 'no tree in view'; g.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })); return g.getAnimations().length > 0; })()`);
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
    if (tag === "desktop") report.contrast_ready = await contrast("#chips .chip, #run");
  }
  await viewport(1440, 900);
  await go("/");
  await evaluate(`window.scrollTo(0, document.getElementById('demo').offsetTop)`); await sleep(500);
  const idx = { nothing: 0, planted: 1, restart: 2 }[example];
  await until(`document.querySelectorAll('#chips .chip').length >= 3`, 10000);
  await evaluate(`document.querySelectorAll('#chips .chip')[${idx}].click(); document.getElementById('run').click(); true`);
  const t0 = Date.now();
  report.timings.gate_loaded_and_search_started_ms = await until(`!!document.querySelector('#spot .note-line:not([hidden])') && /of /.test(document.querySelector('#spot .note-line').textContent)`, 120000);
  await sleep(1500); await shot("4-demo-search");
  report.search = await evaluate(`({ tree_stems: document.querySelectorAll('#garden .stem').length, bed_drawn: (() => { const c = document.querySelector('.bed-cv'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i]) n++; return n; })() })`);
  await until(`/^replay/.test(document.querySelector('#spot .note-line')?.textContent ?? '')`, 120000); await sleep(1200); await shot("5-demo-null");
  await until(`!!document.querySelector('#verdict-word:not([hidden])')`, 180000);
  report.timings.click_to_verdict_ms = Date.now() - t0;
  await sleep(1600); await shot("6-demo-verdict");
  report.verdict = await evaluate(`({ word: document.getElementById('verdict-word').textContent, labels: [...document.querySelectorAll('#spot .note:not([hidden])')].map((d) => d.textContent),
    blossoms_open: document.querySelectorAll('#garden .blossom.open').length, blossoms: document.querySelectorAll('#garden .blossom').length,
    twigs: document.querySelectorAll('#garden .real .twig').length })`);
  report.contrast_verdict = await contrast("#spot .note, #verdict-word, #chips .chip, #run");
  // a background tree shakes and sheds; a cable strikes (vibration and a bolt on the effects canvas)
  report.shake = await evaluate(`(() => { const g = document.querySelector('#wood2 .real .stem'); g.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    return document.querySelectorAll('#wood2 [data-stem="' + g.dataset.stem + '"]')[0].getAnimations().length > 0; })()`);
  await evaluate(`document.querySelector('#city .cable-hit').dispatchEvent(new MouseEvent('click', { bubbles: true, clientX: 500, clientY: 100 })); true`);
  await sleep(150);
  report.bolt_drawn = await evaluate(`(() => { const c = document.getElementById('fx'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i]) n++; return n; })()`);
  await sleep(1200);
  // the cursor as wind: a fast swipe across the bed's ground (nothing is spawned; pieces only move)
  for (let x = 200; x <= 1240; x += 40) { await send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y: 780 }, page); await sleep(8); }
  await sleep(300); await shot("6b-wind");
  // into the run: the ring turns the scene blue from the tree out, then the zoom; out with Esc (via
  // history), the colour draining back; then in by the bed and out with Back
  report.zoom_profile = await frameProfile("enter-run", async () => { await evaluate(`document.querySelector('#garden .real .stem').dispatchEvent(new MouseEvent('click', { bubbles: true })); true`); }, 1500);
  await until(`!document.getElementById('inside').hidden && !document.getElementById('scene').getAnimations().length`, 6000);
  report.zoom_is = await evaluate(`({ scene_transform: getComputedStyle(document.getElementById('scene')).transform, motion_ms: getComputedStyle(document.getElementById('demo')).getPropertyValue('--T'),
    front_last_ms: Math.max(...[...document.querySelectorAll('#demo [data-tide]')].map((e) => parseFloat(e.style.getPropertyValue('--d')) || 0)), ring_drawn: false })`);
  await sleep(600); await shot("7-inside-run");
  report.inside = await evaluate(`({ in_run: document.getElementById('demo').classList.contains('in-run'), title: document.getElementById('run-title')?.textContent,
    moves: document.querySelectorAll('#inside li').length, focus_in: document.activeElement?.id === 'run-title', hash: location.hash,
    tree_blue: getComputedStyle(document.querySelector('#garden .real .twig')).stroke, wood_blue: getComputedStyle(document.querySelector('#wood2 .real .twig')).stroke,
    cable_pink: getComputedStyle(document.querySelector('#city .cable .lit')).stroke })`);
  // a run with several trees: the far left first and lit, the arrow keys and a click on a tree move between them
  report.trees = await evaluate(`(async () => {
    const where = () => document.querySelector('#inside .where').textContent, lit = () => document.querySelectorAll('#garden .real [data-stem]:not(.dimmed)').length;
    const nav = !document.querySelector('#inside .trees').hidden, out = { nav, first: nav ? where() : null, lit_first: lit() };
    if (!nav) return out;
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' })); out.after_right = where();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft' })); document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft' })); out.wraps_left = where();
    document.querySelector('#garden .real .stem[data-stem="4"]').dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await new Promise((r) => setTimeout(r, 100));
    out.after_click = where(); out.still_open = !document.getElementById('inside').hidden; out.lit_one = lit();
    return out; })()`);
  await evaluate(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })); true`);
  await until(`document.getElementById('inside').hidden && !document.getElementById('demo').classList.contains('tiding') && !document.body.classList.contains('inside-open')`, 8000); await sleep(200);
  report.trees.undimmed_after = await evaluate(`document.querySelectorAll('#garden .dimmed').length === 0`);
  report.inside.closed_by_esc = await evaluate(`document.body.dataset.page === 'two' && location.hash === '' && !document.getElementById('demo').classList.contains('in-run')`);
  await evaluate(`document.getElementById('bed').dispatchEvent(new MouseEvent('click', { bubbles: true })); true`);
  await until(`!document.getElementById('inside').hidden && !document.getElementById('scene').getAnimations().length`, 8000); await sleep(400);
  await evaluate(`history.back(); true`);
  await until(`document.getElementById('inside').hidden && !document.body.classList.contains('inside-open')`, 8000);
  report.inside.closed_by_back = true;
  await evaluate(`window.scrollTo(0, document.getElementById('record').offsetTop); true`); await sleep(400); await shot("8-record");
  await go(`/result.html?ex=${example}`);
  await until(`!!document.querySelector('#verdict-word:not([hidden])')`, 180000); await sleep(1600);
  await shot("9-result", true);
  for (const p of ["/docs.html", "/privacy.html", "/terms.html", "/run.html", "/viewer.html", "/nope.html"]) { await go(p); }
  report.author = await evaluate(`({ name: document.querySelector('.who span.by')?.textContent, mail: document.querySelector('.who a[href^="mailto:"]')?.getAttribute('href'), linkedin: document.querySelector('.who a[href*="linkedin.com"]')?.href, safe: document.querySelector('.who a[href*="linkedin.com"]')?.rel })`);
  report.paper_link = await evaluate(`[...document.querySelectorAll('a')].filter(a => a.textContent === 'Paper').every(a => a.href.startsWith('https://papers.ssrn.com/') && a.target === '_blank' && a.rel.includes('noopener') && a.rel.includes('noreferrer'))`);
  await go("/docs.html"); await shot("10-docs");
  await viewport(390, 844); await go("/"); await shot("11-phone-overview");
  await evaluate(`window.scrollTo(0, document.getElementById('demo').offsetTop)`); await sleep(900); await shot("12-phone-demo");
  report.phone_overflow = await evaluate(`document.documentElement.scrollWidth > innerWidth`);
  // reduced motion: still pieces, the run entered and left as a cross-fade, a strike without travel
  await viewport(1440, 900);
  await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] }, page);
  await go("/");
  await evaluate(`window.scrollTo(0, document.getElementById('demo').offsetTop); document.body.dataset.page = 'two'; true`); await sleep(500);
  await until(`document.querySelectorAll('#chips .chip').length >= 3`, 10000);
  await evaluate(`document.getElementById('run').click(); true`);
  await until(`!!document.querySelector('#verdict-word:not([hidden])')`, 180000); await sleep(400);
  await evaluate(`document.querySelector('#garden .real .stem').dispatchEvent(new MouseEvent('click', { bubbles: true })); true`);
  await until(`!document.getElementById('inside').hidden && document.getElementById('demo').classList.contains('in-run')`, 4000); await sleep(400);
  await shot("13-reduced-inside");
  await evaluate(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })); true`);
  await until(`document.getElementById('inside').hidden && !document.body.classList.contains('inside-open')`, 4000);
  report.reduced = await evaluate(`({ out: !document.getElementById('demo').classList.contains('in-run'), scene: getComputedStyle(document.getElementById('scene')).transform })`);
  await send("Emulation.setEmulatedMedia", { features: [] }, page);
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
