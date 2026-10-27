"""Build the observable-garden wheel the site loads, from the repository's own source at HEAD.

    python3 app/web/scripts/build_wheel.py

- Builds from `git archive HEAD`, never the working tree, and refuses if the package source
  (quixote/, sancho/, pyproject.toml) has uncommitted changes: the wheel is the committed code.
- Leaves out the package data under quixote/engine/garden/data: the audit path never reads it.
- Puts the full commit hash into the wheel's metadata as its local version, 0.1.0+g<commit>.
- Writes app/web/public/py/<wheel> and app/web/public/py/MANIFEST.json (file, sha256, bytes,
  commit), removing any earlier wheel. `scripts/check_wheel.mjs` checks both at build time.

The build uses pip's isolated build environment (it fetches setuptools for the build only); the
desktop install is not touched.
"""
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "app" / "web" / "public" / "py"
SOURCE = ["quixote", "sancho", "pyproject.toml", "LICENSE", "README.md"]


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True, text=True).stdout.strip()


def main() -> None:
    dirty = git("status", "--porcelain", "--", "quixote", "sancho", "pyproject.toml")
    if dirty:
        sys.exit(f"refusing: the package source has uncommitted changes:\n{dirty}")
    commit = git("rev-parse", "HEAD")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "src"
        src.mkdir()
        archive = subprocess.run(["git", "archive", "HEAD", "--", *SOURCE], cwd=REPO, check=True,
                                 capture_output=True).stdout
        subprocess.run(["tar", "-x", "-C", str(src)], input=archive, check=True)
        data = src / "quixote" / "engine" / "garden" / "data"
        if data.exists():
            subprocess.run(["rm", "-rf", str(data)], check=True)
        py = src / "pyproject.toml"
        text = py.read_text()
        text, n = re.subn(r'(?m)^version = "([^"+]+)"$', lambda m: f'version = "{m.group(1)}+g{commit}"', text, count=1)
        if n != 1:
            sys.exit("pyproject.toml has no static version line to stamp")
        text = re.sub(r'(?ms)^\[tool\.setuptools\.package-data\]\n(?:[^\[\n].*\n)*', "", text)
        py.write_text(text)
        wheels = Path(tmp) / "wheels"
        subprocess.run([sys.executable, "-m", "pip", "wheel", str(src), "--no-deps", "-q", "-w", str(wheels)],
                       check=True)
        (built,) = wheels.glob("*.whl")
        OUT.mkdir(parents=True, exist_ok=True)
        for old in OUT.glob("*.whl"):
            old.unlink()
        dest = OUT / built.name
        dest.write_bytes(built.read_bytes())
    blob = dest.read_bytes()
    man = {"wheel": dest.name, "sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob), "commit": commit,
           "built_from": "git archive HEAD of quixote/, sancho/, pyproject.toml, without quixote/engine/garden/data"}
    (OUT / "MANIFEST.json").write_text(json.dumps(man, indent=1) + "\n")
    print(f"wrote {dest.relative_to(REPO)} ({len(blob):,} bytes) from {commit[:12]}")


if __name__ == "__main__":
    main()
