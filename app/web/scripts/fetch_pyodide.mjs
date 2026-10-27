// Puts the pinned Pyodide files into public/pyodide/<version>/ and checks every one against
// public/pyodide/MANIFEST.json. The version in the path is what makes them safe to cache as immutable. Core files come from the release's core archive, package wheels
// from the release's distribution; a file already present is only checked. Any mismatch stops
// the build. This runs at build time only: the site serves these files itself.
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync, copyFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "pyodide");
const man = JSON.parse(readFileSync(join(root, "MANIFEST.json"), "utf8"));
const dir = join(root, man.pyodide);
mkdirSync(dir, { recursive: true });
const sha = (b) => createHash("sha256").update(b).digest("hex");
const ok = (f) => existsSync(join(dir, f.file)) && sha(readFileSync(join(dir, f.file))) === f.sha256;

async function get(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return Buffer.from(await r.arrayBuffer());
}

const missing = man.files.filter((f) => !ok(f));
const core = missing.filter((f) => !f.package);
if (core.length) {
  const tar = await get(man.core_archive.url);
  if (sha(tar) !== man.core_archive.sha256) throw new Error("the Pyodide core archive's sha256 does not match the manifest");
  const tmp = mkdtempSync(join(tmpdir(), "pyodide-core-"));
  writeFileSync(join(tmp, "core.tar.bz2"), tar);
  execFileSync("tar", ["xjf", "core.tar.bz2"], { cwd: tmp });
  for (const f of core) copyFileSync(join(tmp, "pyodide", f.file), join(dir, f.file));
  rmSync(tmp, { recursive: true, force: true });
}
for (const f of missing.filter((f) => f.package)) writeFileSync(join(dir, f.file), await get(f.from));

const bad = man.files.filter((f) => !ok(f));
if (bad.length) throw new Error("sha256 mismatch: " + bad.map((f) => f.file).join(", "));
console.log(`pyodide ${man.pyodide}: ${man.files.length} files present and matching the manifest`);
