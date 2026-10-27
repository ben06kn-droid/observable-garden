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
const chrome = spawn(chromePath, ["--headless=new", "--remote-debugging-port=0", `--user-data-dir=${profile}`, "--no-first-run", "--hide-scrollbars", "about:blank"],
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
const note = (where, kind, text) => issues.push({ where, kind, text: String(text).slice(0, 400) });
ws.addEventListener("message", async (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && waiting.has(m.id)) { const w = waiting.get(m.id); waiting.delete(m.id); m.error ? w.rej(new Error(m.error.message)) : w.res(m.result); return; }
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
  report.probe = await evaluate(probe);
  chrome.kill(); srv.close();
  console.log(JSON.stringify(report.probe, null, 1)); process.exit(0);
}
try {
  for (const [vw, vh, tag] of [[1440, 900, "desktop"], [1366, 768, "laptop"]]) {
    await viewport(vw, vh);
    await go("/");
    await sleep(600);
    await shot(`${tag}-1-overview-top`);
    // page one scrolls freely to its last line, and page two stays plain paper meanwhile
    const oneEnd = await evaluate(`document.getElementById('demo').offsetTop - innerHeight`);
    if (oneEnd > 0) { await evaluate(`window.scrollTo(0, ${oneEnd}); true`); await sleep(500); await shot(`${tag}-2-overview-end`); }
    report[`${tag}_page_one_scrolls_freely`] = oneEnd <= 0 || (await evaluate(`Math.abs(scrollY - ${Math.max(0, oneEnd)}) < 2`));
    report[`${tag}_paper_until_snap`] = await evaluate(`document.body.dataset.page === 'one'`);
    // leaving page one glides onto page two, and the night switches on only at the end
    await evaluate(`window.scrollBy(0, 80); true`);
    await sleep(120);
    report[`${tag}_still_paper_mid_glide`] = await evaluate(`document.body.dataset.page === 'one'`);
    await until(`document.body.dataset.page === 'two'`, 5000);
    report[`${tag}_snapped`] = await evaluate(`Math.abs(scrollY - document.getElementById('demo').offsetTop) < 3`);
    await sleep(300);
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
  await sleep(1600); await shot("4-demo-search");
  await until(`document.getElementById('phase').textContent === 'The null'`, 120000); await sleep(400); await shot("5-demo-null");
  await until(`document.getElementById('phase').textContent === 'The verdict'`, 180000);
  report.timings.click_to_verdict_ms = Date.now() - t0;
  await sleep(1800); await shot("6-demo-verdict");
  report.verdict = await evaluate(`({ word: document.getElementById('big').textContent, line: document.getElementById('line').textContent, card: document.querySelector('#verdict .word')?.textContent })`);
  report.streaks_gone = await evaluate(`!document.getElementById('streaks')`);
  // into a tree: blue, then the zoom; out again with Esc
  await evaluate(`document.querySelector('#garden .real .stem .move:last-child .bud')?.dispatchEvent(new MouseEvent('click', { bubbles: true })); true`);
  await sleep(250);
  report.inside = { blue_first: await evaluate(`!!document.querySelector('#garden .real .stem.selected')`) };
  await until(`!document.getElementById('inside').hidden`, 5000);
  await sleep(1300); await shot("7-inside-tree");
  report.inside.open = await evaluate(`document.getElementById('inside').classList.contains('open')`);
  report.inside.title = await evaluate(`document.getElementById('inside-title')?.textContent`);
  report.inside.moves = await evaluate(`document.querySelectorAll('#inside li').length`);
  report.inside.focus_in = await evaluate(`document.activeElement?.id === 'inside-title'`);
  await evaluate(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })); true`);
  await until(`document.getElementById('inside').hidden`, 5000); await sleep(200);
  report.inside.closed_by_esc = await evaluate(`!document.querySelector('#garden .real .stem.selected') && document.body.dataset.page === 'two'`);
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
