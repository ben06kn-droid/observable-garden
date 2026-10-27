// Checks the committed wheel against public/py/MANIFEST.json, and, where git history is
// available, that the package source has not changed since the commit the wheel was built from
// (if it has, rebuild with `npm run build-wheel` after committing).
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const dir = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "py");
const man = JSON.parse(readFileSync(join(dir, "MANIFEST.json"), "utf8"));
const blob = readFileSync(join(dir, man.wheel));
if (createHash("sha256").update(blob).digest("hex") !== man.sha256) throw new Error(`${man.wheel}: sha256 does not match public/py/MANIFEST.json`);
if (!man.wheel.includes(`+g${man.commit}`)) throw new Error(`${man.wheel}: its version does not carry the commit ${man.commit}`);

let changed = null;
try {
  execFileSync("git", ["cat-file", "-e", `${man.commit}^{commit}`], { stdio: "ignore" });
  changed = execFileSync("git", ["diff", "--name-only", man.commit, "HEAD", "--", "quixote", "sancho", "pyproject.toml"],
                         { cwd: join(dir, "..", "..", "..", ".."), encoding: "utf8" }).trim();
} catch {
  console.warn(`check_wheel: commit ${man.commit.slice(0, 12)} is not in this checkout's history; source check skipped`);
}
if (changed) throw new Error(`the package source changed since the wheel was built (${man.commit.slice(0, 12)}):\n${changed}\nrebuild: npm run build-wheel`);
console.log(`wheel ${man.wheel}: matches its manifest${changed === "" ? ", built from the package source at HEAD" : ""}`);
