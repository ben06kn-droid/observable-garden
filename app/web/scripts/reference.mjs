// Reference screenshots of the chain's pages, for checking that a restructuring changes nothing a visitor sees.
// Each page at its top, middle and end, at 1440x900 and 390x844 (2x), in Chrome, served under vercel.json's
// headers. Two sets: reduced motion (every scene drawn once and still, so the shots can be compared pixel for
// pixel) and full motion 5 s after load (for looking at; animated scenes never repeat a frame). On the one-page
// site each page is a section ([data-section]), and top, middle and end are taken within the section.
//   node scripts/reference.mjs --out DIR [--root DIST] [--pages home,run,docs,sancho] [--motion]
// Compare two sets with: node scripts/reference.mjs --compare A B
import { spawn } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync, rmSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { inflateSync } from "node:zlib";
import { serve } from "./serve_dist.mjs";

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const PATHS = { home: "/", run: "/run.html", docs: "/docs.html", sancho: "/sancho.html" };

// ---- compare: PNG decode (8-bit RGB/RGBA, no interlace, as Chrome writes them) and a per-pixel difference
function png(file) {
  const b = readFileSync(file); let p = 8, w = 0, h = 0, ct = 0; const idat = [];
  while (p < b.length) {
    const len = b.readUInt32BE(p), type = b.toString("ascii", p + 4, p + 8), d = b.subarray(p + 8, p + 8 + len);
    if (type === "IHDR") { w = d.readUInt32BE(0); h = d.readUInt32BE(4); ct = d[9]; }
    if (type === "IDAT") idat.push(d);
    p += 12 + len;
  }
  const bpp = ct === 6 ? 4 : 3, raw = inflateSync(Buffer.concat(idat)), out = Buffer.alloc(w * h * 3), stride = w * bpp;
  let prev = Buffer.alloc(stride);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (stride + 1)], line = Buffer.from(raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1)));
    for (let x = 0; x < stride; x++) {
      const a = x >= bpp ? line[x - bpp] : 0, up = prev[x], c = x >= bpp ? prev[x - bpp] : 0;
      const pp = a + up - c, pa = Math.abs(pp - a), pb = Math.abs(pp - up), pc = Math.abs(pp - c);
      const paeth = pa <= pb && pa <= pc ? a : pb <= pc ? up : c;
      line[x] = (line[x] + (f === 1 ? a : f === 2 ? up : f === 3 ? (a + up) >> 1 : f === 4 ? paeth : 0)) & 255;
    }
    for (let x = 0; x < w; x++) for (let k = 0; k < 3; k++) out[(y * w + x) * 3 + k] = line[x * bpp + k];
    prev = line;
  }
  return { w, h, px: out };
}
if (process.argv.includes("--compare")) {
  const [a, b] = process.argv.slice(process.argv.indexOf("--compare") + 1);
  const rows = [];
  for (const f of readdirSync(a).filter((f) => f.endsWith(".png"))) {
    let A, B; try { A = png(join(a, f)); B = png(join(b, f)); } catch { rows.push({ shot: f, missing: true }); continue; }
    if (A.w !== B.w || A.h !== B.h) { rows.push({ shot: f, size: `${A.w}x${A.h} vs ${B.w}x${B.h}` }); continue; }
    // anti-aliasing: a difference only where an edge is (some neighbour differs in A by more than the change). A
    // section of the one-page site can start a fraction of a pixel lower than its page did (the sections above it
    // need not end on a whole pixel), which moves every glyph's anti-aliasing: B is tried shifted by up to 2 device
    // pixels up or down, and the best match is reported with its shift
    let best = null;
    for (const shift of [0, -1, 1, -2, 2]) {
      const r = diff(A, B, shift);
      if (!best || r.over < best.over) best = { ...r, shift };
      if (r.over === 0) break;
    }
    rows.push({ shot: f, differing_pixels: best.over, share: +(100 * best.over / (A.w * A.h)).toFixed(3), max: best.max, shift_px: best.shift });
  }
  for (const r of rows) console.log(JSON.stringify(r));
  process.exit(0);
}
function diff(A, B, shift) {
    let over = 0, max = 0;
    for (let i = 0; i < A.w * A.h; i++) {
      const x0 = i % A.w, y0 = (i / A.w) | 0, yb = y0 + shift;
      if (yb < 0 || yb >= B.h) continue;
      const ib = yb * A.w + x0;
      let d = 0; for (let k = 0; k < 3; k++) d = Math.max(d, Math.abs(A.px[i * 3 + k] - B.px[ib * 3 + k]));
      if (d <= 8) continue;
      const x = i % A.w, y = (i / A.w) | 0; let edge = false;
      for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const j = (y + dy) * A.w + (x + dx); if (x + dx < 0 || x + dx >= A.w || y + dy < 0 || y + dy >= A.h) continue;
        let e = 0; for (let k = 0; k < 3; k++) e = Math.max(e, Math.abs(A.px[i * 3 + k] - A.px[j * 3 + k]));
        if (e >= d) edge = true;
      }
      if (!edge) { over++; max = Math.max(max, d); }
    }
    return { over, max };
}

// ---- capture
const out = arg("--out"), root = arg("--root", join(import.meta.dirname, "..", "dist"));
const pages = arg("--pages", "home,run,docs,sancho").split(","), motion = process.argv.includes("--motion");
// --at DIR: take each shot at the same offset into the page (or section) as DIR's shots were (its offsets.json), so a
// page whose length changed is still compared content for content; this run's own offsets go to offsets.json
const at0 = arg("--at", null), given = at0 ? JSON.parse(readFileSync(join(at0, "offsets.json"), "utf8")) : null, offsets = {};
mkdirSync(out, { recursive: true });
const port = 5600 + Math.floor(Math.random() * 300);
const srv = await serve(port, { root });
const profile = mkdtempSync(join(tmpdir(), "qx-ref-"));
const chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", ["--headless=new", "--remote-debugging-port=0", `--user-data-dir=${profile}`, "--no-first-run", "--hide-scrollbars", "about:blank"], { stdio: "ignore" });
let wsUrl;
for (let i = 0; i < 100 && !wsUrl; i++) { try { const p = readFileSync(join(profile, "DevToolsActivePort"), "utf8").split("\n")[0]; wsUrl = (await (await fetch(`http://127.0.0.1:${p}/json/list`)).json()).find((t) => t.type === "page")?.webSocketDebuggerUrl; } catch { await sleep(100); } }
const ws = new WebSocket(wsUrl); await new Promise((r) => ws.addEventListener("open", r, { once: true }));
let id = 0; const pend = new Map();
ws.addEventListener("message", (e) => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } });
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async (expression) => (await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true })).result?.result?.value;

// the same randomness on every load (home's fallen leaves are scattered at random), so two captures of one build match
await send("Page.addScriptToEvaluateOnNewDocument", { source: `(() => { let s = 20261117; Math.random = () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; })();` });
for (const [tag, w, h, dpr, mobile] of [["desktop", 1440, 900, 1, false], ["phone", 390, 844, 2, true]]) {
  await send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: dpr, mobile });
  await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: motion ? "no-preference" : "reduce" }] });
  for (const page of pages) {
    await send("Page.navigate", { url: `http://127.0.0.1:${port}${PATHS[page]}` });
    // loaded, fonts in, the loading screen (if any) gone, the scenes drawn
    for (let i = 0; i < 100; i++) { if (await evaluate(`document.readyState === "complete" && !document.querySelector(".loader")`)) break; await sleep(100); }
    await evaluate("document.fonts.ready.then(() => true)");
    // the run page: once the gate has loaded and filled in the prompt (its layout changes when it does)
    if (page === "run") for (let i = 0; i < 600; i++) { if (await evaluate(`(document.getElementById("f-prompt")?.value.length ?? 1) > 0`)) break; await sleep(100); }
    await sleep(motion ? 5000 : 1500);
    for (const at of ["top", "middle", "end"]) {
      const name = `${page}-${at}-${tag}`, want = given ? given[name] : null;
      offsets[name] = await evaluate(`(() => { const s = document.querySelector('[data-section="${page}"]');
        const top = s ? s.getBoundingClientRect().top + scrollY : 0, len = s ? s.offsetHeight : document.documentElement.scrollHeight;
        const span = Math.max(0, len - innerHeight), off = ${want ?? "null"} ?? ({ top: 0, middle: Math.round(span / 2), end: span })["${at}"];
        scrollTo(0, top + off); return off; })()`);
      await sleep(motion ? 800 : 500);
      const s = await send("Page.captureScreenshot", { format: "png" });
      writeFileSync(join(out, `${page}-${at}-${tag}.png`), Buffer.from(s.result.data, "base64"));
    }
    console.log(tag, page);
  }
}
writeFileSync(join(out, "offsets.json"), JSON.stringify(offsets, null, 1));
ws.close(); chrome.kill(); srv.close(); setTimeout(() => rmSync(profile, { recursive: true, force: true }), 1000);
