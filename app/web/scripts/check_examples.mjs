// Every served example equals its repository source, byte for byte, and its manifest entry.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const web = join(dirname(fileURLToPath(import.meta.url)), "..");
const repo = join(web, "..", "..");
const sha = (p) => createHash("sha256").update(readFileSync(p)).digest("hex");
const { files } = JSON.parse(readFileSync(join(web, "public", "examples", "MANIFEST.json"), "utf8"));
const bad = files.filter((f) => sha(join(repo, f.source)) !== f.sha256 || sha(join(web, "public", "examples", f.file)) !== f.sha256);
if (bad.length) throw new Error("example copies differ from their sources (run npm run copy-examples): " + bad.map((f) => f.source).join(", "));
console.log(`examples: ${files.length} copies equal their sources`);
