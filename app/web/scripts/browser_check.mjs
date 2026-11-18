// Drives the built site in headless Chrome under vercel.json's headers and reports what a visitor
// would hit: console errors, exceptions and content-security-policy violations (from the page and
// from the gate's worker), how long the gate takes, and screenshots of each stage.
//   node scripts/browser_check.mjs [--shots DIR] [--example nothing|planted|restart] [--chrome PATH]
//   node scripts/browser_check.mjs --run-page        the run page against the mock providers
//   node scripts/browser_check.mjs --pages --fixtures DIR   the Sancho page's editor and the viewer
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { inflateSync } from "node:zlib";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { serve } from "./serve_dist.mjs";
import { serveLocal } from "./mock_providers.mjs";

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const shots = arg("--shots", null);
const example = arg("--example", "nothing");
const chromePath = arg("--chrome", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome");
if (shots) mkdirSync(shots, { recursive: true });

const port = 4100 + Math.floor(Math.random() * 800);
const runPage = process.argv.includes("--run-page");   // the full run against the mock provider (scripts/mock_anthropic.mjs)
// --base URL: check a deployed site (a Vercel preview) instead of serving dist/ locally
const remote = arg("--base", null);
const srv = remote ? { close() {} } : await serve(port, { mock: runPage });
// the Local provider's mock: an OpenAI-compatible server on its own loopback port, as Ollama would be
const localPort = port + 1000;
const localSrv = runPage && !remote ? await serveLocal(localPort) : { close() {} };
const base = remote ? remote.replace(/\/$/, "") : `http://127.0.0.1:${port}`;
const profile = mkdtempSync(join(tmpdir(), "qx-check-"));
const headed = process.argv.includes("--headed");   // a real window, for the frame profile
// --uncapped: no vsync and no frame-rate limit, so a profile shows how many frames the page can make
// and what the worst one costs, even when the machine's display clock is throttled (a sleeping or
// locked display paces headless Chrome at 30 Hz)
const uncapped = process.argv.includes("--uncapped") ? ["--disable-frame-rate-limit", "--disable-gpu-vsync"] : [];
// on CI only: a downloaded Chrome on Ubuntu 24.04 runners cannot start its sandbox (AppArmor), and the
// one page it loads is this site's own build
const ci = process.env.CI ? ["--no-sandbox"] : [];
// --analytics with --headed: Chrome as a plain visitor (navigator.webdriver false), so Vercel's script sends its beacons
const visitor = process.argv.includes("--analytics") && headed ? ["--disable-blink-features=AutomationControlled"] : [];
const chrome = spawn(chromePath, [...(headed ? ["--window-size=1366,868"] : ["--headless=new"]), ...uncapped, ...ci, ...visitor, "--remote-debugging-port=0", `--user-data-dir=${profile}`, "--no-first-run", "--hide-scrollbars", "about:blank"],
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
const requests = [];
// every response of 400 or more, by URL. The one 404 the check asks for itself is /nope.html (the 404
// page under the CSP); any other is a page or a file the site is missing, and fails the check. The mock
// providers' deliberate errors (the run page's error cases) are answers, not missing files.
const failedLoads = [];
const insights = [], insightMethod = new Map();   // every /_vercel/insights/ response: the analytics script and its page-view beacon
const analytics = () => ({
  script: [...new Set(insights.filter((r) => r.url.endsWith("/script.js")).map((r) => `${r.status} ${r.url}`))],
  view: insights.filter((r) => new URL(r.url).pathname === "/_vercel/insights/view").map((r) => `${r.status} ${r.method} ${r.url}`),
  // the package's debug script, or anything else of Vercel's from another host: must stay empty
  other_hosts: [...new Set(requests.filter((r) => /vercel|insights/.test(r.url) && new URL(r.url).origin !== base).map((r) => r.url))],
});
// nothing analytics-related from another host, ever; on a deployment, the script loaded; and when Chrome runs as
// a plain visitor (--analytics --headed; Vercel's script sends nothing to a headless or automated browser), page views were sent
const analyticsFails = (a) => a.other_hosts.length > 0 || (remote && !a.script.some((x) => x.startsWith("200 ")))
  || (visitor.length > 0 && !a.view.some((x) => /^2\d\d /.test(x)));
// Vercel serves /_vercel/insights/ (the analytics script and its beacon) only on a deployment: served
// locally it is missing by design; on a deployment (--base) it must load.
const INTENDED = (u) => u.endsWith("/nope.html") || u.includes("/__mock/") || /^http:\/\/localhost:\d+\/v1\//.test(u)
  || (!remote && new URL(u).pathname.startsWith("/_vercel/insights/"));
// locally, the missing script's 404 page is refused as a script (MIME type, nosniff): the same absence, not a CSP violation
const INTENDED_REFUSAL = (t) => !remote && /^Refused to execute script from '[^']*\/_vercel\/insights\/script\.js' because its MIME type/.test(t);
const missing = () => failedLoads.filter((f) => !INTENDED(f.url));
const note = (where, kind, text) => issues.push({ where, kind, text: String(text).slice(0, 400) });
ws.addEventListener("message", async (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && waiting.has(m.id)) { const w = waiting.get(m.id); waiting.delete(m.id); m.error ? w.rej(new Error(m.error.message)) : w.res(m.result); return; }
  if (m.method === "Tracing.dataCollected") { traceEvents.push(...m.params.value); return; }
  if (m.method === "Tracing.tracingComplete") { traceDone?.(); return; }
  const where = m.sessionId ?? "browser";
  if (m.method === "Network.requestWillBeSent" && m.params.request.url.includes("/_vercel/insights/")) insightMethod.set(m.params.requestId, m.params.request.method);
  if (m.method === "Network.responseReceived" && m.params.response.url.includes("/_vercel/insights/"))
    insights.push({ url: m.params.response.url, status: m.params.response.status, method: insightMethod.get(m.params.requestId) ?? "?" });
  if (m.method === "Target.attachedToTarget") {
    const sid = m.params.sessionId; sessions.add(sid);
    await send("Runtime.enable", {}, sid).catch(() => {});
    await send("Log.enable", {}, sid).catch(() => {});
    await send("Network.enable", {}, sid).catch(() => {});      // the worker's requests too
    await send("Runtime.runIfWaitingForDebugger", {}, sid).catch(() => {});
    await send("Target.setAutoAttach", { autoAttach: true, waitForDebuggerOnStart: false, flatten: true }, sid).catch(() => {});
  } else if (m.method === "Network.requestWillBeSent") requests.push({ url: m.params.request.url, method: m.params.request.method, headers: m.params.request.headers });
  else if (m.method === "Network.responseReceived" && m.params.response.status >= 400) failedLoads.push({ url: m.params.response.url, status: m.params.response.status });
  else if (m.method === "Runtime.exceptionThrown") note(where, "exception", m.params.exceptionDetails?.exception?.description ?? m.params.exceptionDetails?.text);
  else if (m.method === "Runtime.consoleAPICalled" && ["error", "warning"].includes(m.params.type)) note(where, "console." + m.params.type, m.params.args.map((a) => a.value ?? a.description).join(" "));
  else if (m.method === "Log.entryAdded" && ["error", "warning"].includes(m.params.entry.level)) note(where, "log." + m.params.entry.source, m.params.entry.text);
});

const { targetId } = await send("Target.createTarget", { url: "about:blank" });
const { sessionId: page } = await send("Target.attachToTarget", { targetId, flatten: true });
for (const d of ["Runtime", "Log", "Page", "Network"]) await send(`${d}.enable`, {}, page);
await send("Target.setAutoAttach", { autoAttach: true, waitForDebuggerOnStart: false, flatten: true }, page);
const evaluate = async (expr) => (await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true }, page)).result.value;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function viewport(w, h) { await send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 600 }, page); }
async function go(path) {
  const loaded = new Promise((r) => { const f = (ev) => { const m = JSON.parse(ev.data); if (m.method === "Page.loadEventFired" && m.sessionId === page) { ws.removeEventListener("message", f); r(); } }; ws.addEventListener("message", f); });
  await send("Page.navigate", { url: base + path }, page);
  await loaded;
  await evaluate("document.fonts.ready.then(() => true)");
  // the one-page site (home, run): built behind its loading screen, which goes once everything is drawn
  for (let i = 0; i < 300 && await evaluate(`!!document.querySelector(".loader")`); i++) await sleep(50);
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
// --analytics: every page once, then what Vercel Web Analytics loaded and sent, and the CSP. Vercel's
// script sends nothing when navigator.webdriver is set or the user agent says "Headless", so on a
// deployment run this with --headed (Chrome without automation flags) to see the page-view beacons.
if (process.argv.includes("--analytics")) {
  try {
    await viewport(1440, 900);
    const pages = ["/", "/demo.html", "/eucalyptus.html", "/docs.html", "/sancho.html", "/run.html", "/viewer.html", "/privacy.html", "/terms.html", "/share.html", "/result.html?ex=" + example];
    for (const p of pages) { await go(p); await sleep(1500); }
    report.visitor = await evaluate(`({ webdriver: navigator.webdriver, headless_ua: navigator.userAgent.includes("Headless"), storage_keys: Object.keys(localStorage).concat(Object.keys(sessionStorage)), cookies: document.cookie })`);
    await sleep(1500);
  } catch (e) { report.error = String(e.message ?? e); }
  const exited = new Promise((r) => chrome.once("exit", r));
  chrome.kill(); srv.close();
  await Promise.race([exited, sleep(5000)]);
  report.csp_violations = issues.filter((i) => /Content Security Policy|Refused to/i.test(i.text) && !INTENDED_REFUSAL(i.text)).length;
  report.issues = issues.slice(0, 10);
  report.missing = missing();
  report.analytics = analytics();
  console.log(JSON.stringify(report, null, 1));
  process.exit(report.error || report.csp_violations || report.missing.length || analyticsFails(report.analytics) ? 1 : 0);
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

// --pages --fixtures DIR: the Sancho page's lever editor and the viewer. DIR holds result.json
// (quixote audit --json on examples/logs/scripted_session.json, B 500) and sancho_out/sancho.json
// (quixote sancho on a panel long enough for it); the log, panel and class are examples/'. Without --fixtures, the
// Sancho editor alone.
if (process.argv.includes("--pages")) {
  const fx = arg("--fixtures", null), ex = join(import.meta.dirname, "..", "..", "..", "examples");
  const setFiles = async (paths) => {
    const { result } = await send("Runtime.evaluate", { expression: "document.getElementById('v-files')" }, page);
    await send("DOM.enable", {}, page);
    await send("DOM.setFileInputFiles", { files: paths, objectId: result.objectId }, page);
  };
  try {
    await viewport(1440, 900);
    await go("/sancho.html");
    await until(`/^[0-9a-f]{64}$/.test(document.getElementById('cfg-hash').textContent)`, 10000);
    const state = () => evaluate(`({ hash: document.getElementById('cfg-hash').textContent, kind: document.getElementById('cfg-kind').textContent,
      problems: document.getElementById('lever-problems').textContent, download_disabled: document.getElementById('cfg-download').disabled,
      rows: document.getElementById('cfg-rows').textContent, cmd: document.getElementById('cfg-cmd').textContent })`);
    report.sancho = { levers: await evaluate(`[...document.querySelectorAll('.lever .lever-name')].map((e) => e.textContent)`),
      default_hash: await evaluate(`document.getElementById('default-hash').textContent`), registered: await state() };
    await shot("sancho-1", true);
    const setLever = (name, value) => evaluate(`(() => { const l = [...document.querySelectorAll('.lever')].find((x) => x.querySelector('.lever-name').textContent === '${name}');
      const c = l.querySelector('input:not([type=checkbox]), select, textarea'); c.value = ${JSON.stringify(value)}; c.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
    await setLever("horizon", "1"); await sleep(300);
    report.sancho.tailored = await state();
    await setLever("rates", "0.3, abc"); await sleep(300);
    report.sancho.bad_rates = await state();
    await evaluate(`document.getElementById('cfg-reset').click(); true`); await sleep(300);
    report.sancho.after_reset = (await state()).hash === report.sancho.registered.hash;
    // the download: the file the page writes, read back; its hash (the page's canonical form) is the one shown
    const dl = mkdtempSync(join(tmpdir(), "qx-dl-"));
    await send("Browser.setDownloadBehavior", { behavior: "allow", downloadPath: dl, eventsEnabled: true });
    await setLever("horizon", "20"); await sleep(300);
    const shown = (await state()).hash;
    await evaluate(`document.getElementById('cfg-download').click(); true`); await sleep(1200);
    const text = readFileSync(join(dl, "sancho_config.json"), "utf8");
    const L = await import("../src/levers.ts");
    report.sancho.download = { bytes: text.length, horizon: JSON.parse(text).horizon, hash_matches_shown: (await L.configSha256(JSON.parse(text))) === shown };
    if (fx) writeFileSync(join(fx, "tailored_config.json"), text);       // for the equivalence check against sancho.config, if wanted

    // the viewer needs the fixtures (a result and a Sancho run, made by the package); without them it is skipped
    if (fx) {
    await go("/viewer.html");
    await setFiles([join(ex, "logs", "scripted_session.json"), join(fx, "result.json"), join(ex, "data", "tiny_panel.npz"), join(ex, "class.json")]);
    await until(`!document.getElementById('v-record').hidden`, 90000); await sleep(1500);
    report.viewer_search = await evaluate(`({ files: [...document.querySelectorAll('#v-list li')].map((e) => e.textContent.split(' · ')[0]), error: document.getElementById('v-error').textContent,
      word: document.getElementById('verdict-word')?.textContent, labels: [...document.querySelectorAll('#spot .note:not([hidden])')].map((e) => e.textContent),
      twigs: document.querySelectorAll('#garden .real .twig').length, meaning: document.getElementById('v-meaning').textContent,
      record: [...document.querySelectorAll('#v-kv dt')].map((d) => d.textContent + ': ' + d.nextElementSibling.textContent), cmd: document.getElementById('v-cmd').textContent })`);
    await evaluate(`window.scrollTo(0, document.getElementById('demo').offsetTop); true`); await sleep(500); await shot("viewer-search");
    await go("/viewer.html");
    await setFiles([join(fx, "sancho_out", "sancho.json")]);
    await until(`!document.getElementById('v-record').hidden`, 30000); await sleep(800);
    report.viewer_sancho = await evaluate(`({ error: document.getElementById('v-error').textContent, bonsai: !!document.querySelector('#garden .bonsai'),
      label: document.querySelector('#garden .bonsai-label')?.textContent, heading: document.getElementById('v-rec-h').textContent, meaning: document.getElementById('v-meaning').textContent,
      record: [...document.querySelectorAll('#v-kv dt')].map((d) => d.textContent + ': ' + d.nextElementSibling.textContent), cmd: document.getElementById('v-cmd').textContent })`);
    await evaluate(`window.scrollTo(0, document.getElementById('demo').offsetTop); true`); await sleep(500); await shot("viewer-sancho");
    await evaluate(`window.scrollTo(0, 0); true`); await sleep(300); await shot("viewer-sancho-full", true);
    } else report.viewer = "skipped: no --fixtures";
    // every page at phone width (375 px): no horizontal scroll, and the header's links inside the header
    await viewport(375, 740);
    report.phone = {};
    for (const pg of ["/", "/demo.html", "/eucalyptus.html", "/docs.html", "/sancho.html", "/run.html", "/viewer.html", "/privacy.html"]) {
      await go(pg); await sleep(400);
      // the menu on a phone: the control and, open, its panel inside the screen, sized for touch (44 px)
      report.phone[pg] = await evaluate(`(() => { const b = document.querySelector('.menu-btn'); b.click(); const p = document.querySelector('.menu-panel').getBoundingClientRect(), r = b.getBoundingClientRect();
        const items = [...document.querySelectorAll('.menu-panel a')].map((a) => Math.round(a.getBoundingClientRect().height)); b.click();
        return { page_scrolls_sideways: document.documentElement.scrollWidth > innerWidth, panel_inside: p.right <= innerWidth + 0.5 && p.left >= 0, control_h: Math.round(r.height), item_h_min: Math.min(...items) }; })()`);
      if (pg === "/sancho.html") await shot("sancho-phone");
    }
    report.network = { requests: requests.length, elsewhere: [...new Set(requests.map((r) => new URL(r.url).origin).filter((o) => o !== base && !o.startsWith("data:") && !o.startsWith("blob:")))] };
  } catch (e) { report.error = String(e.message ?? e); }
  const exited = new Promise((r) => chrome.once("exit", r));
  chrome.kill(); srv.close();
  await Promise.race([exited, sleep(5000)]);
  try { rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 }); } catch { /* temporary */ }
  report.csp_violations = issues.filter((i) => /Content Security Policy|Refused to/i.test(i.text) && !INTENDED_REFUSAL(i.text)).length;
  report.issues = issues.filter((i) => !/404/.test(i.text)).slice(0, 10);
  report.missing = missing();
  report.analytics = analytics();
  console.log(JSON.stringify(report, null, 1));
  process.exit(report.error || report.csp_violations || report.missing.length || analyticsFails(report.analytics) || issues.some((i) => i.kind === "exception") ? 1 : 0);
}

// the run page's gate loads for a visitor who comes to its form: a field taking focus starts it at once
async function gateIn() {
  await evaluate(`(() => { const f = document.getElementById('f-moves'); f.focus({ preventScroll: true }); f.blur(); return true; })()`);
  await until(`document.getElementById('f-prompt').value.length > 100 && /rows/.test(document.getElementById('in-status').textContent)`, 60000);
}
async function wheel(dy) { await send("Input.dispatchMouseEvent", { type: "mouseWheel", x: 400, y: 400, deltaX: 0, deltaY: dy }, page); }
if (runPage) {
  // The run page end to end, under the production headers, with the provider replaced by the mock:
  // the bundled inputs checked, a bad key, a rate limit, a cancel, then a complete run; the key never
  // appears in the page, the URL or storage; every request goes to the site (the mock is served
  // from it) or the provider; the share link opens as an unverified result.
  const KEY = "sk-ant-test-0123456789abcdef";
  try {
    await viewport(1440, 900);
    await go("/run.html?provider=mock");
    await gateIn();
    report.inputs = await evaluate(`({ status: document.getElementById('in-status').textContent, cap: document.getElementById('in-cap').textContent, estimate: document.getElementById('estimate').textContent, start_enabled: !document.getElementById('start').disabled })`);
    await shot("run-1-setup", true);
    const startWith = async (k, moves = 8) => evaluate(`(() => { document.getElementById('f-key').value = ${JSON.stringify(k)}; document.getElementById('f-moves').value = '${moves}'; document.getElementById('f-B').value = '500'; document.getElementById('run-form').requestSubmit(); return true; })()`);
    await startWith("");
    report.no_key = await evaluate(`document.getElementById('run-error').textContent`);
    for (const [k, name] of [["sk-ant-bad", "bad_key"], ["sk-ant-ratelimit", "rate_limit"], ["sk-ant-nocredit", "no_credit"], ["sk-ant-badversion", "bad_version"]]) {
      await startWith(k);
      await until(`!document.getElementById('start').disabled && document.getElementById('run-error').textContent.length > 0`, 60000);
      report[name] = await evaluate(`({ message: document.getElementById('run-error').textContent, key_field: document.getElementById('f-key').value, record_hidden: document.getElementById('record').hidden })`);
    }
    await startWith(KEY);
    await until(`document.querySelectorAll('#run-log li.move').length >= 2`, 60000);
    await evaluate(`document.getElementById('cancel').click(); true`);
    await until(`!document.getElementById('start').disabled`, 10000);
    report.cancel = await evaluate(`({ message: document.getElementById('run-error').textContent, record_hidden: document.getElementById('record').hidden, key_field: document.getElementById('f-key').value })`);
    const t0 = Date.now();
    await startWith(KEY, 12);
    await until(`!document.getElementById('record').hidden`, 240000);
    report.run_ms = Date.now() - t0;
    await sleep(1500);
    report.run = await evaluate(`({ word: document.getElementById('verdict-word')?.textContent, labels: [...document.querySelectorAll('#spot .note:not([hidden])')].map((e) => e.textContent),
      moves: document.querySelectorAll('#run-log li.move').length, tokens: document.getElementById('tokens').textContent,
      record: [...document.querySelectorAll('#rec-kv dt')].map((d) => d.textContent + ': ' + d.nextElementSibling.textContent),
      cmd: document.getElementById('rec-cmd').textContent, twigs: document.querySelectorAll('#garden .real .twig').length })`);
    await evaluate(`window.scrollTo(0, document.getElementById('demo').offsetTop); true`); await sleep(600); await shot("run-2-verdict");
    await evaluate(`window.scrollTo(0, document.getElementById('record').offsetTop - 60); true`); await sleep(300); await shot("run-3-record");
    report.prompt_default = await evaluate(`[...document.querySelectorAll('#rec-kv dt')].find((d) => d.textContent === 'Prompt')?.nextElementSibling.textContent`);
    // an edited prompt is a different search, and the record says so
    await evaluate(`(() => { const p = document.getElementById('f-prompt'); p.value = p.value + ' Prefer short searches.'; p.dispatchEvent(new Event('input')); return true; })()`);
    await startWith(KEY, 6);
    await until(`!document.getElementById('record').hidden && !document.getElementById('start').disabled`, 240000);
    await sleep(500);
    report.prompt_edited = await evaluate(`[...document.querySelectorAll('#rec-kv dt')].find((d) => d.textContent === 'Prompt')?.nextElementSibling.textContent`);
    report.key_gone = await evaluate(`({ in_text: document.body.innerText.includes(${JSON.stringify(KEY)}), in_html: document.documentElement.outerHTML.includes(${JSON.stringify(KEY)}),
      in_url: location.href.includes(${JSON.stringify(KEY)}), local: localStorage.length, session: Object.keys(sessionStorage),
      in_storage: [...Object.values(localStorage), ...Object.values(sessionStorage)].some((v) => v.includes(${JSON.stringify(KEY)})), field: document.getElementById('f-key').value })`);   // session: only the loading screen's "seen" flag
    // the share link: copied (or shown, where the clipboard is not allowed), then opened
    await send("Browser.grantPermissions", { permissions: ["clipboardReadWrite", "clipboardSanitizedWrite"], origin: base }).catch(() => {});
    const shareUrl = await evaluate(`(async () => { document.getElementById('share').click(); await new Promise((r) => setTimeout(r, 400));
      const t = document.getElementById('share-out').textContent; if (t.startsWith('http')) return t; try { return await navigator.clipboard.readText(); } catch { return null; } })()`);
    report.share = { length: shareUrl?.length ?? null, has_key: !!shareUrl?.includes(KEY), fragment_only: !!shareUrl && new URL(shareUrl).search === "" };
    if (shareUrl) {
      await go(new URL(shareUrl).pathname + new URL(shareUrl).hash);
      await until(`document.querySelectorAll('#sh-body dd').length > 5`, 10000);
      report.share.page = await evaluate(`({ unverified: document.getElementById('sh-note').textContent.includes('Unverified'), word: document.querySelector('.share-word')?.textContent,
        rows: [...document.querySelectorAll('#sh-body dt')].map((d) => d.textContent) })`);
      await shot("run-4-share", true);
    }
    // the other providers: OpenAI (the Responses API), OpenRouter and a local server (chat completions).
    // For each: an error shown word for word, then a complete run; the record names the provider,
    // the effort and the host.
    const OTHER = { openai: "sk-test-openai-0123456789", openrouter: "sk-or-test-0123456789" };
    report.providers = {};
    const record = () => evaluate(`({ word: document.getElementById('verdict-word')?.textContent, moves: document.querySelectorAll('#run-log li.move').length,
      record: Object.fromEntries([...document.querySelectorAll('#rec-kv dt')].map((d) => [d.textContent, d.nextElementSibling.textContent])),
      estimate: document.getElementById('estimate').textContent, key_host: document.getElementById('key-host').textContent })`);
    const choose = (id) => evaluate(`(() => { const s = document.getElementById('f-provider'); s.value = '${id}'; s.dispatchEvent(new Event('change')); return true; })()`);
    for (const id of ["openai", "openrouter", "local"]) {
      const out = report.providers[id] = {};
      const t0 = Date.now();
      await go("/run.html?provider=mock");
      await gateIn();
      await choose(id);
      out.efforts = await evaluate(`[...document.getElementById('f-effort').options].map((o) => o.value)`);
      out.key_placeholder = await evaluate(`document.getElementById('f-key').placeholder`);
      if (id === "openrouter") {
        out.list_before_key = await evaluate(`[...document.getElementById('f-model').options].map((o) => o.textContent)`);
        await evaluate(`(() => { const k = document.getElementById('f-key'); k.value = '${OTHER.openrouter}'; k.dispatchEvent(new Event('input')); return true; })()`);
        await until(`[...document.getElementById('f-model').options].some((o) => o.value === 'qwen/qwen3-235b-a22b')`, 10000);
        out.list = await evaluate(`[...document.getElementById('f-model').options].map((o) => o.value)`);
        await evaluate(`(() => { const s = document.getElementById('f-model'); s.value = 'qwen/qwen3-235b-a22b'; s.dispatchEvent(new Event('input')); return true; })()`);
      }
      if (id === "local") {
        await evaluate(`(() => { const u = document.getElementById('f-local'); u.value = 'http://example.com:11434/v1'; u.dispatchEvent(new Event('input'));
          document.getElementById('f-model-id').value = 'qwen3:32b'; return true; })()`);
        await startWith("");
        out.not_local = await evaluate(`document.getElementById('run-error').textContent`);
        await evaluate(`(() => { const u = document.getElementById('f-local'); u.value = 'http://localhost:${localPort}/v1'; u.dispatchEvent(new Event('input')); return true; })()`);
      } else {
        await evaluate(`document.getElementById('f-effort').value = 'none'; true`);
        await startWith(OTHER[id] + "-badeffort");
        await until(`!document.getElementById('start').disabled && document.getElementById('run-error').textContent.length > 0`, 60000);
        out.bad_effort = await evaluate(`document.getElementById('run-error').textContent`);
        await startWith(OTHER[id] + "-nocredit");
        await until(`!document.getElementById('start').disabled && document.getElementById('run-error').textContent.length > 0`, 60000);
        out.no_credit = await evaluate(`document.getElementById('run-error').textContent`);
        await evaluate(`document.getElementById('f-effort').value = 'high'; true`);
      }
      await startWith(id === "local" ? "" : OTHER[id], 10);
      await until(`!document.getElementById('record').hidden && !document.getElementById('start').disabled`, 240000);
      await sleep(800);
      Object.assign(out, await record(), { ms: Date.now() - t0 });
      await evaluate(`window.scrollTo(0, document.getElementById('demo').offsetTop); true`); await sleep(500); await shot(`run-provider-${id}`);
    }
    const mockHosts = [base, `http://localhost:${localPort}`];
    const model = requests.filter((r) => r.url.includes("/__mock/") && !r.url.endsWith("/models") || r.url.startsWith(`http://localhost:${localPort}/`));
    const keys = [KEY, "sk-ant-bad", "sk-ant-ratelimit", "sk-ant-nocredit", "sk-ant-badversion", ...Object.values(OTHER).flatMap((k) => [k, k + "-badeffort", k + "-nocredit"])];
    report.network = { requests: requests.length, model_calls: model.length,
      by_host: Object.fromEntries([...new Set(requests.map((r) => new URL(r.url).origin))].map((o) => [o, requests.filter((r) => new URL(r.url).origin === o).length])),
      elsewhere: [...new Set(requests.map((r) => new URL(r.url).origin).filter((o) => !mockHosts.includes(o) && !o.startsWith("data:") && !o.startsWith("blob:")))],
      key_only_in_header: model.filter((r) => r.method === "POST").every((r) => {
        const h = Object.fromEntries(Object.entries(r.headers).map(([k, v]) => [k.toLowerCase(), v]));
        if (r.url.includes("/__mock/anthropic/")) return keys.includes(h["x-api-key"]) && !h.authorization;
        if (r.url.startsWith(`http://localhost:${localPort}/`)) return !h.authorization && !h["x-api-key"];
        return keys.includes(String(h.authorization ?? "").replace(/^Bearer /, "")) && !h["x-api-key"];
      }),
      models_list_without_key: requests.filter((r) => r.url.endsWith("/api/v1/models")).every((r) => !Object.keys(r.headers).some((k) => /authorization|x-api-key/i.test(k))),
      key_in_any_url: requests.some((r) => keys.some((k) => r.url.includes(k))) };
  } catch (e) { report.error = String(e.message ?? e); }
  const exited = new Promise((r) => chrome.once("exit", r));
  chrome.kill(); srv.close(); localSrv.close();
  await Promise.race([exited, sleep(5000)]);
  try { rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 }); } catch { /* temporary */ }
  report.csp_violations = issues.filter((i) => /Content Security Policy|Refused to/i.test(i.text) && !INTENDED_REFUSAL(i.text)).length;
  report.issues = issues.filter((i) => !/404/.test(i.text)).slice(0, 10);
  report.missing = missing();
  report.analytics = analytics();
  console.log(JSON.stringify(report, null, 1));
  process.exit(report.error || report.csp_violations || report.missing.length || analyticsFails(report.analytics) || issues.some((i) => i.kind === "exception") ? 1 : 0);
}

try {
  // ---- the one-page site (src/onepage/): home, run, docs and Sancho are sections of one document, built once behind
  // the loading screen; each keeps its address.
  const step = (s) => process.stderr.write(`[chain] ${s}\n`);   // progress, on stderr
  const here = () => evaluate(`location.pathname === "/index.html" ? "/" : location.pathname`);
  const toEnd = () => evaluate(`window.scrollTo(0, document.documentElement.scrollHeight); true`);
  const within = (p, ms) => Promise.race([p.catch(() => null), sleep(ms).then(() => null)]);   // a page that navigated away never answers
  const push = async (dy, n = 10) => { for (let i = 0; i < n; i++) { await within(wheel(dy / n), 250); await sleep(16); } };
  const arrive = async (path) => { const t0 = Date.now(); while (Date.now() - t0 < 8000) { if (await within(here(), 400) === path && await within(evaluate(`document.readyState === "complete" && !document.querySelector(".loader")`), 400)) return true; await sleep(50); } return false; };
  const runTop = `Math.round(document.querySelector('[data-section="run"]').getBoundingClientRect().top + scrollY)`;
  const settledAt = async (expr, ms = 5000) => { try { await until(expr, ms); return true; } catch { return false; } };
  for (const [vw, vh, tag] of [[1440, 900, "desktop"], [1366, 768, "laptop"]]) {
    await viewport(vw, vh);
    // a first visit in the session: the whole loading screen (at least the 1.5 s of the B), then the site, at home
    await evaluate(`sessionStorage.clear(); true`);
    const t0 = Date.now();
    await send("Page.navigate", { url: base + "/" }, page);
    await sleep(300);
    const one = report[`${tag}_onepage`] = { first_visit: { loader_shown: await evaluate(`!!document.querySelector(".loader") && !document.documentElement.dataset.loader`) } };
    await until(`document.readyState === "complete" && !document.querySelector(".loader")`, 20000);
    Object.assign(one.first_visit, { loader_ms: Date.now() - t0, at_home: await evaluate(`scrollY < 2`), path: await here(), title: await evaluate(`document.title`) });
    await shot(`${tag}-1-home`);
    // the trees do not respond: a click or Enter starts nothing, and they are neither buttons nor under a pointer cursor
    if (tag === "desktop") report.trees_still_home = await evaluate(`(() => { const g = [...document.querySelectorAll('#bg-trees .real .stem')].find((e) => { const r = e.getBoundingClientRect(); return r.left > 800 && r.top < innerHeight; });
      if (!g) return 'no tree in view'; g.dispatchEvent(new MouseEvent('click', { bubbles: true })); g.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
      return { animations: g.getAnimations().length, cursor: getComputedStyle(g).cursor, focusable: g.hasAttribute('tabindex'), role: g.getAttribute('role') }; })()`);
    if (tag === "desktop") {
      // the run page's gate (Pyodide) loads only for a visitor who comes to its form: none for one who scrolls past it
      // to the end and waits there; then the form held on screen starts it (focus and Start: --run-page)
      step("desktop: the gate loads on demand");
      const end = await evaluate(`document.documentElement.scrollHeight - innerHeight`);
      for (let y = 0; y <= end + 240; y += 240) { await evaluate(`scrollTo(0, ${Math.min(y, end)}); true`); await sleep(60); }
      await sleep(2500);
      one.gate_scrolled_past = await evaluate(`performance.getEntriesByType("mark").map((m) => m.name).filter((n) => n.startsWith("qx-gate"))`);
      await evaluate(`document.getElementById('run-form').scrollIntoView({ block: 'center' }); true`);
      one.gate_on_view = await settledAt(`performance.getEntriesByName("qx-gate-start:view").length > 0`, 6000);
      await evaluate(`scrollTo(0, 0); true`); await sleep(500);
    }
    step(`${tag}: addresses follow the scroll`);
    const h0 = await evaluate(`history.length`);
    await evaluate(`scrollTo(0, ${runTop} + 200); true`); await sleep(400);
    one.scroll_into_run = { path: await here(), title: await evaluate(`document.title`), current: await evaluate(`document.querySelector('.menu-panel a[aria-current]')?.textContent ?? null`) };
    await evaluate(`scrollTo(0, 0); true`); await sleep(400);
    one.scroll_back_home = { path: await here(), current: await evaluate(`document.querySelector('.menu-panel a[aria-current]')?.textContent ?? null`), history_unchanged: (await evaluate(`history.length`)) === h0 };
    step(`${tag}: a header link, Back, the cue, the keyboard`);
    await evaluate(`document.querySelector('.menu-panel a[href="/run.html"]').click(); true`);
    one.header_link = { arrived: await settledAt(`Math.abs(scrollY - ${runTop}) < 2`), path: await here(), history_added: (await evaluate(`history.length`)) === h0 + 1, y: await evaluate(`Math.round(scrollY)`), run_top: await evaluate(runTop) };
    await evaluate(`history.back(); true`);
    one.back = { home: await settledAt(`scrollY < 2 && location.pathname === "/"`) };
    await evaluate(`document.querySelector('[data-section="home"] a.cue').click(); true`);
    one.cue = { arrived: await settledAt(`Math.abs(scrollY - ${runTop}) < 2`), path: await here(), y: await evaluate(`Math.round(scrollY)`), run_top: await evaluate(runTop) };
    await evaluate(`history.back(); true`); await settledAt(`scrollY < 2 && location.pathname === "/"`); await sleep(300);
    await evaluate(`document.querySelector('[data-section="home"] a.cue').focus(); true`); await sleep(200);
    await send("Input.dispatchKeyEvent", { type: "keyDown", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13 }, page);
    await send("Input.dispatchKeyEvent", { type: "keyUp", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13 }, page);
    one.enter_on_cue = await settledAt(`Math.abs(scrollY - ${runTop}) < 2 && location.pathname === "/run.html"`);
    one.focus_moved = await evaluate(`document.activeElement?.dataset?.section ?? document.activeElement?.className ?? null`);
    step(`${tag}: a direct link, later in the session`);
    const t1 = Date.now();
    await send("Page.navigate", { url: base + "/run.html" }, page); await sleep(200);
    one.direct_run = { formed: await evaluate(`document.documentElement.dataset.loader === "formed"`) };
    await until(`document.readyState === "complete" && !document.querySelector(".loader")`, 20000);
    Object.assign(one.direct_run, { loader_ms: Date.now() - t1, at_run: await evaluate(`Math.abs(scrollY - ${runTop}) < 2`), title: await evaluate(`document.title`) });
    await shot(`${tag}-2-run`);
    // every address, as a direct link later in the session: the finished B, then its own section
    const secTop = (n) => `Math.round(document.querySelector('[data-section="${n}"]').getBoundingClientRect().top + scrollY)`;
    one.direct = {};
    for (const [n, path] of [["docs", "/docs.html"], ["sancho", "/sancho.html"]]) {
      await go(path);
      one.direct[n] = { at_section: await evaluate(`Math.abs(scrollY - ${secTop(n)}) < 2`), title: await evaluate(`document.title`), current: await evaluate(`document.querySelector('.menu-panel a[aria-current]')?.textContent ?? null`) };
    }
    // the address follows the scroll through every section, adding no history
    const h1 = await evaluate(`history.length`), seenPaths = [];
    for (const n of ["home", "run", "docs", "sancho"]) { await evaluate(`scrollTo(0, ${secTop(n)} + 100); true`); await sleep(400); seenPaths.push(await here()); }
    one.scroll_through = { paths: seenPaths, history_unchanged: (await evaluate(`history.length`)) === h1 };
    // the header's Docs and Sancho links scroll in place; a link in the contents lands on its heading, its anchor kept
    await evaluate(`scrollTo(0, 0); true`); await sleep(400);
    await evaluate(`document.querySelector('.menu-panel a[href="/docs.html"]').click(); true`);
    one.header_docs = await settledAt(`Math.abs(scrollY - ${secTop("docs")}) < 2 && location.pathname === "/docs.html"`);
    await evaluate(`document.querySelector('.menu-panel a[href="/sancho.html"]').click(); true`);
    one.header_sancho = await settledAt(`Math.abs(scrollY - ${secTop("sancho")}) < 2 && location.pathname === "/sancho.html"`);
    await go("/docs.html");
    const anchor = await evaluate(`(() => { const a = [...document.querySelectorAll('[data-section="docs"] .toc a')].at(-2); a.click(); return a.hash; })()`);
    one.contents_link = { anchor, arrived: await settledAt(`(() => { const h = document.getElementById(decodeURIComponent(location.hash.slice(1))); return !!h && Math.abs(h.getBoundingClientRect().top - (parseFloat(getComputedStyle(h).scrollMarginTop) || 0)) < 3; })()`), url: await evaluate(`location.pathname + location.hash`) };
    await shot(`${tag}-3-docs`);
  }
  await viewport(1440, 900);
  {
    // after both passes: their history checks count entries, and Chrome keeps at most 50
    const one = report.desktop_onepage, secTop = (n) => `Math.round(document.querySelector('[data-section="${n}"]').getBoundingClientRect().top + scrollY)`;
    // out of the one page to the demo (from the run section) and to Eucalyptus (from home), and Back: the two must
    // return alike (the page kept or rebuilt the same way, the same loading screen, on the section left from)
    step("desktop: the menu by keyboard and pointer");
    {
      await go("/");
      const key = async (k, code, vk) => { for (const type of ["keyDown", "keyUp"]) await send("Input.dispatchKeyEvent", { type, key: k, code, windowsVirtualKeyCode: vk }, page); await sleep(80); };
      const state = () => evaluate(`({ expanded: document.querySelector('.menu-btn').getAttribute('aria-expanded'), hidden: document.querySelector('.menu-panel').hidden, focus: document.activeElement?.textContent?.trim() ?? null })`);
      const m = one.menu = { roles: await evaluate(`({ button: document.querySelector('.menu-btn').tagName, controls: document.querySelector('.menu-btn').getAttribute('aria-controls') === document.querySelector('.menu-panel').id, nav_label: document.querySelector('.menu-panel').getAttribute('aria-label'), items: [...document.querySelectorAll('.menu-panel a')].map((a) => a.textContent), current: document.querySelector('.menu-panel a[aria-current]')?.textContent })`) };
      await evaluate(`document.querySelector('.menu-btn').focus(); true`);
      await key("Enter", "Enter", 13); m.enter_opens = await state();                 // focus on the current item (Quixote)
      await key("ArrowDown", "ArrowDown", 40); m.arrow_down = await state();          // Run
      await key("End", "End", 35); m.end = await state();                             // Eucalyptus
      await key("Escape", "Escape", 27); m.escape = await state();                    // closed, focus on the button
      await key("ArrowDown", "ArrowDown", 40); m.down_opens = await state();
      await send("Input.dispatchMouseEvent", { type: "mousePressed", x: 900, y: 600, button: "left", clickCount: 1 }, page);
      await send("Input.dispatchMouseEvent", { type: "mouseReleased", x: 900, y: 600, button: "left", clickCount: 1 }, page); await sleep(150);
      m.outside_closes = await state();
      const r = await evaluate(`(() => { const b = document.querySelector('.menu-btn').getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; })()`);
      for (const type of ["mousePressed", "mouseReleased"]) await send("Input.dispatchMouseEvent", { type, x: r[0], y: r[1], button: "left", clickCount: 1 }, page);
      await sleep(200); m.click_opens = await state();
      const d = await evaluate(`(() => { const a = document.querySelector('.menu-panel a[href="/docs.html"]').getBoundingClientRect(); return [a.left + a.width / 2, a.top + a.height / 2]; })()`);
      for (const type of ["mousePressed", "mouseReleased"]) await send("Input.dispatchMouseEvent", { type, x: d[0], y: d[1], button: "left", clickCount: 1 }, page);
      m.choose_docs = { arrived: await settledAt(`Math.abs(scrollY - ${secTop("docs")}) < 2 && location.pathname === "/docs.html"`), ...(await state()), current: await evaluate(`document.querySelector('.menu-panel a[aria-current]')?.textContent`) };
      m.ok = m.roles.button === "BUTTON" && m.roles.controls && m.roles.items.join() === "Quixote,Run,Docs,Sancho,Paper,Eucalyptus" && m.roles.current === "Quixote"
        && m.enter_opens.expanded === "true" && m.enter_opens.focus === "Quixote" && m.arrow_down.focus === "Run" && m.end.focus === "Eucalyptus"
        && m.escape.hidden && m.escape.focus?.startsWith("Garden") && m.down_opens.focus === "Quixote" && m.outside_closes.hidden && !m.click_opens.hidden
        && m.choose_docs.arrived && m.choose_docs.hidden && m.choose_docs.current === "Docs";
    }
    step("desktop: out to the demo and to Eucalyptus, and Back");
    const outAndBack = async (from, name, link, to) => {
      await go(from);
      await evaluate(`window.__stay = 1; true`);
      await evaluate(`document.querySelector('[data-section="${name}"] ${link}').click(); true`);
      const arrived = await settledAt(`location.pathname === "${to}" && document.readyState === "complete"`, 20000); await sleep(800);
      const there = { arrived, theme: await evaluate(`document.documentElement.dataset.theme`), main_empty: await evaluate(`document.querySelector("main").children.length === 0`),
        canvases: await evaluate(`document.querySelectorAll("canvas").length`), wake: await evaluate(`!!document.querySelector(".wake-layer")`) };
      await evaluate(`history.back(); true`);
      const back = await settledAt(`location.pathname === "${from}" && document.readyState === "complete" && !document.querySelector(".loader")`, 20000); await sleep(800);
      return { ...there, back: { arrived: back, path: await here(), page_kept: await evaluate(`window.__stay === 1`), loader: await evaluate(`document.documentElement.dataset.loader ?? null`),
        at_section: await evaluate(`Math.abs(scrollY - ${secTop(name)}) < 2`), title: await evaluate(`document.title`) } };
    };
    const demo = await outAndBack("/run.html", "run", 'a[href="/demo.html"]', "/demo.html");
    const euc = await outAndBack("/", "home", 'a[href="/eucalyptus.html"]', "/eucalyptus.html");
    one.out_and_back = { demo, eucalyptus: euc,
      eucalyptus_page: euc.theme === "home" && euc.main_empty && euc.canvases === 0 && !euc.wake,
      same_return: demo.back.arrived && euc.back.arrived && demo.back.at_section && euc.back.at_section && demo.back.page_kept === euc.back.page_kept && demo.back.loader === euc.back.loader };
  }
  await go("/demo.html"); await sleep(500);
  report.contrast_ready = await contrast("#chips .chip, #run");
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
  // the background trees do not respond: a click starts nothing, no pointer cursor, not focusable
  report.trees_still_demo = await evaluate(`(() => { const g = document.querySelector('#wood2 .real .stem'); g.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    const all = [...document.querySelectorAll('#wood2 [data-stem="' + g.dataset.stem + '"]')];
    return { animations: all.reduce((n, e) => n + e.getAnimations().length, 0), cursor: getComputedStyle(g).cursor, focusable: !!document.querySelector('#wood2 [tabindex]'), hit_areas: document.querySelectorAll('#wood2 .hit').length }; })()`);
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
  report.inside.closed_by_esc = await evaluate(`location.hash === '' && !document.getElementById('demo').classList.contains('in-run')`);
  await evaluate(`document.getElementById('bed').dispatchEvent(new MouseEvent('click', { bubbles: true })); true`);
  await until(`!document.getElementById('inside').hidden && !document.getElementById('scene').getAnimations().length`, 8000); await sleep(400);
  await evaluate(`history.back(); true`);
  await until(`document.getElementById('inside').hidden && !document.body.classList.contains('inside-open')`, 8000);
  report.inside.closed_by_back = true;
  await evaluate(`window.scrollTo(0, document.getElementById('record').offsetTop); true`); await sleep(400); await shot("8-record");
  await go(`/result.html?ex=${example}`);
  await until(`!!document.querySelector('#verdict-word:not([hidden])')`, 180000); await sleep(1600);
  await shot("9-result", true);
  // the menu's pill on every page: its ground (alpha 1 is the page's own ground; docs and Sancho their glass and sheet,
  // with what lies beneath blurred), its ink, and no full-width bar
  report.menu_pill = {};
  for (const p of ["/", "/demo.html", "/eucalyptus.html", "/docs.html", "/sancho.html", "/privacy.html", "/terms.html", "/run.html", "/viewer.html", "/share.html", `/result.html?ex=${example}`]) {
    await go(p);
    report.menu_pill[p] = await evaluate(`(() => { const b = document.querySelector('.menu-btn'), cs = getComputedStyle(b), t = document.querySelector('.top').getBoundingClientRect();
      return { ground: cs.backgroundColor, ink: cs.color, blur: cs.backdropFilter !== 'none', width: Math.round(t.width), no_bar: t.width < innerWidth / 3 }; })()`);
  }
  await go("/nope.html");                                    // on purpose: the 404 page itself, under the CSP
  report.not_found_page = await evaluate(`document.title`);
  // the author's name, Contact and LinkedIn: in the footer only, never in the menu (a page with both: Eucalyptus)
  await go("/eucalyptus.html");
  report.author = await evaluate(`({ email_not_shown: !document.body.innerText.includes('@'), in_menu: !!document.querySelector('.top .who, .top a[href^="mailto:"], .top a[href*="linkedin.com"]'),
    name: document.querySelector('.foot .who span')?.textContent, contact: document.querySelector('.foot .who a[href^="mailto:"]')?.textContent, linkedin: document.querySelector('.foot .who a[href*="linkedin.com"]')?.href, safe: document.querySelector('.foot .who a[href*="linkedin.com"]')?.rel })`);
  report.paper_link = await evaluate(`[...document.querySelectorAll('a')].filter(a => a.textContent === 'Paper').every(a => a.href.startsWith('https://papers.ssrn.com/') && a.target === '_blank' && a.rel.includes('noopener') && a.rel.includes('noreferrer'))`);
  await go("/docs.html"); await shot("10-docs");
  await viewport(390, 844); await go("/"); await shot("11-phone-home");
  await go("/demo.html"); await sleep(900); await shot("12-phone-demo");
  report.phone_overflow = await evaluate(`document.documentElement.scrollWidth > innerWidth`);
  // reduced motion: still pieces, the run entered and left as a cross-fade, a strike without travel
  await viewport(1440, 900);
  await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] }, page);
  await go("/demo.html"); await sleep(500);
  await until(`document.querySelectorAll('#chips .chip').length >= 3`, 10000);
  await evaluate(`document.getElementById('run').click(); true`);
  await until(`!!document.querySelector('#verdict-word:not([hidden])')`, 180000); await sleep(400);
  await evaluate(`document.querySelector('#garden .real .stem').dispatchEvent(new MouseEvent('click', { bubbles: true })); true`);
  await until(`!document.getElementById('inside').hidden && document.getElementById('demo').classList.contains('in-run')`, 4000); await sleep(400);
  await shot("13-reduced-inside");
  await evaluate(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })); true`);
  await until(`document.getElementById('inside').hidden && !document.body.classList.contains('inside-open')`, 4000);
  report.reduced = await evaluate(`({ out: !document.getElementById('demo').classList.contains('in-run'), scene: getComputedStyle(document.getElementById('scene')).transform })`);
  // reduced motion on the one page: a link to a section jumps there at once
  await go("/"); await evaluate(`document.querySelector('.menu-panel a[href="/run.html"]').click(); true`); await sleep(120);
  report.reduced.onepage_jump = await evaluate(`Math.abs(scrollY - Math.round(document.querySelector('[data-section="run"]').getBoundingClientRect().top + scrollY)) < 2`);

  report.reduced.still = {};
  for (const p of ["/", "/run.html", "/docs.html", "/sancho.html", "/demo.html", "/eucalyptus.html", "/viewer.html"]) {
    await go(p); await sleep(600);
    report.reduced.still[p] = await evaluate(`document.getAnimations().filter((a) => a.playState === 'running').length`);
    await shot(`reduced-${p.replace(/\W+/g, "") || "home"}`);
  }
  await send("Emulation.setEmulatedMedia", { features: [] }, page);
} catch (e) {
  report.error = String(e.message ?? e);
} finally {
  const exited = new Promise((r) => chrome.once("exit", r));
  chrome.kill(); srv.close();
  await Promise.race([exited, sleep(5000)]);
  try { rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 }); } catch { /* a temporary profile; the OS will clear it */ }
}
report.csp_violations = issues.filter((i) => /Content Security Policy|Refused to/i.test(i.text) && !INTENDED_REFUSAL(i.text)).length;
report.missing = missing();
report.analytics = analytics();
console.log(JSON.stringify(report, null, 1));
process.exit(report.error || report.csp_violations || report.missing.length || analyticsFails(report.analytics) || issues.some((i) => i.kind === "exception") ? 1 : 0);
