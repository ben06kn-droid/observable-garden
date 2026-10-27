// After `vite build`: the built site must carry no inline script, inline event handler, inline
// style or <style> block (the content security policy allows none), must load nothing from another
// origin, and every pinned file it serves (Pyodide, the package wheels, fonts, the examples) must
// match ASSETS.lock.json, which is committed. `node scripts/check_dist.mjs --update` rewrites the
// lock after a deliberate change (a new Pyodide pin, a rebuilt wheel, a font update).
import { createHash } from "node:crypto";
import { readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { join, relative, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const web = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(web, "dist");
const walk = (d) => readdirSync(d).flatMap((n) => { const p = join(d, n); return statSync(p).isDirectory() ? walk(p) : [p]; });
const files = walk(dist).map((p) => relative(dist, p).split("\\").join("/"));
const problems = [];

for (const f of files.filter((f) => f.endsWith(".html"))) {
  const s = readFileSync(join(dist, f), "utf8");
  for (const m of s.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)) {
    if (!/\bsrc=/.test(m[1]) || m[2].trim()) problems.push(`${f}: inline <script>`);
    const src = /\bsrc="([^"]+)"/.exec(m[1]);
    if (src && /^(https?:)?\/\//.test(src[1])) problems.push(`${f}: script from another origin: ${src[1]}`);
  }
  if (/<style\b/i.test(s)) problems.push(`${f}: <style> block`);
  if (/\sstyle\s*=/i.test(s)) problems.push(`${f}: style= attribute`);
  if (/\son[a-z]+\s*=/i.test(s)) problems.push(`${f}: inline event handler`);
  for (const m of s.matchAll(/<(?:link|img|source|iframe|audio|video)\b[^>]*\b(?:href|src)="((?:https?:)?\/\/[^"]+)"/gi)) {
    problems.push(`${f}: loads from another origin: ${m[1]}`);
  }
}
for (const f of files.filter((f) => f.endsWith(".css"))) {
  const s = readFileSync(join(dist, f), "utf8");
  for (const m of s.matchAll(/url\(\s*["']?((?:https?:)?\/\/[^"')]+)/gi)) problems.push(`${f}: url() to another origin: ${m[1]}`);
  if (/url\(\s*["']?data:/i.test(s)) problems.push(`${f}: data: URL`);
}

// pinned files: everything the site serves that is not built from src/
const pinned = files.filter((f) => /^(pyodide|py|examples)\//.test(f) || /\.(woff2?|wasm|whl|zip)$/.test(f))
  .filter((f) => !f.endsWith("MANIFEST.json")).sort();
const sha = (f) => createHash("sha256").update(readFileSync(join(dist, f))).digest("hex");
// fonts get content-hashed names from Vite; key them by their name without the hash
const key = (f) => f.replace(/^assets\/(.+)-[A-Za-z0-9_-]{8}(\.woff2?)$/, "fonts/$1$2");
const now = Object.fromEntries(pinned.map((f) => [key(f), sha(f)]));
const lockPath = join(web, "ASSETS.lock.json");
if (process.argv.includes("--update")) {
  writeFileSync(lockPath, JSON.stringify({ note: "sha256 of every pinned file the built site serves; checked by scripts/check_dist.mjs", files: now }, null, 1) + "\n");
  console.log(`ASSETS.lock.json: ${Object.keys(now).length} files`);
} else {
  const lock = JSON.parse(readFileSync(lockPath, "utf8")).files;
  for (const [k, v] of Object.entries(now)) if (lock[k] !== v) problems.push(`${k}: ${lock[k] ? "sha256 differs from" : "not in"} ASSETS.lock.json`);
  for (const k of Object.keys(lock)) if (!(k in now)) problems.push(`${k}: in ASSETS.lock.json but not served`);
}

const bytes = files.reduce((n, f) => n + statSync(join(dist, f)).size, 0);
if (problems.length) { console.error(problems.join("\n")); process.exit(1); }
console.log(`dist: ${files.length} files, ${(bytes / 1e6).toFixed(1)} MB; no inline script or style, no other origin, ${pinned.length} pinned files match the lock`);
