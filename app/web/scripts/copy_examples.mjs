// Copies the demo's example files from the repository into public/examples/ and writes
// public/examples/MANIFEST.json (source, file, sha256, bytes) and public/examples/demos.json.
// `check_examples.mjs` fails the build (and CI) if a copy differs from its source.
import { createHash } from "node:crypto";
import { copyFileSync, readFileSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { FILES, DEMOS } from "./examples.mjs";

const web = join(dirname(fileURLToPath(import.meta.url)), "..");
const repo = join(web, "..", "..");
const out = join(web, "public", "examples");
const files = FILES.map(([src, name]) => {
  copyFileSync(join(repo, src), join(out, name));
  const b = readFileSync(join(out, name));
  return { source: src, file: name, sha256: createHash("sha256").update(b).digest("hex"), bytes: b.length };
});
writeFileSync(join(out, "MANIFEST.json"), JSON.stringify({ files }, null, 1) + "\n");
writeFileSync(join(out, "demos.json"), JSON.stringify({ demos: DEMOS }, null, 1) + "\n");
console.log(`copied ${files.length} example files`);
