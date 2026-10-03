"""7.5's sealed holdout for the AGENT seeds: generate, seal, and open once.

`prereg/planted-edge.md` build item 2, "The holdout, generated and sealed at
registration". The planted process continues into 2018-2022 with the same planted
member and scale, on the holdout segment's own residual pool, resampled with child [2].
**The seal covers the agent seeds only**; the scripted half computes its holdout inline.

**What is sealed**, per panel seed and level: the holdout segment's planted returns,
`make_draw(base, seed, level).holdout.returns`, bit for bit, as one `.npy` each. That is
the only part of the holdout an agent run's submission needs and cannot get from
elsewhere. The holdout's features are rows of the pinned X, and its population Sharpe
is a closed form of the code. Beside the files, `manifest.json` records each file's
SHA-256, the planted member and scale, the pinned X's SHA-256, the code state and the
platform.

**The seal** is a deterministic `tar.gz` of that directory (sorted names, zeroed times
and owners), so its SHA-256 is a function of the content alone. **The SHA-256 is
written into the registration at stage 2's live commit, before any agent run.**
Encrypting the archive and moving it off the machine is the operator's step, as 6.5's
was (`openssl enc`, the passphrase held by the author). **This module never encrypts,
decrypts or holds a key.** `open_sealed` reads a plaintext archive, after the operator
has decrypted it, and only once its SHA-256 matches the registered one.

**Design block only, for now.** The registered agent seed block is fixed by stage 2's
live commit, and `AGENT_SEEDS` stays `None` until then, so the generator refuses every
seed outside 640000-640999. **Generating the registered archive is not done here.**

    python -m experiments.planted_holdout --seeds 640000-640009 --levels 0 1.5 \\
        --out /tmp/planted_holdout_design
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import tarfile
import time
from pathlib import Path

import numpy as np

from environments import planted_panel as pp

DESIGN = range(640_000, 641_000)
AGENT_SEEDS: range | None = None   # fixed by the stage-2 live commit, not before
REPO = Path(__file__).resolve().parent.parent


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def check_seeds(seeds) -> list[int]:
    seeds = [int(s) for s in seeds]
    allowed = [DESIGN] + ([AGENT_SEEDS] if AGENT_SEEDS is not None else [])
    bad = [s for s in seeds if not any(s in r for r in allowed)]
    if bad:
        raise SystemExit(
            f"seeds {bad[:5]}{'...' if len(bad) > 5 else ''} are outside the design block "
            "640000-640999. The agent seed block is fixed by stage 2's live commit; until "
            "then this generator makes design archives only (prereg/planted-edge.md).")
    if len(set(seeds)) != len(seeds):
        raise SystemExit("a seed appears twice")
    return seeds


def check_levels(levels) -> list[float]:
    levels = [float(x) for x in levels]
    bad = [x for x in levels if x not in pp.LEVELS]
    if bad or not levels:
        raise SystemExit(f"levels {bad or levels} are not among the registered {pp.LEVELS}")
    return levels


def check_out(out: Path) -> Path:
    """Outside the repository, and new. A plaintext holdout inside the tree is one
    `git add -A` from being published."""
    out = Path(out).resolve()
    if out == REPO or REPO in out.parents:
        raise SystemExit(f"{out} is inside the repository; the holdout is written outside it")
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} exists and is not empty; refused rather than mixed")
    return out


def _npy_bytes(a: np.ndarray) -> bytes:
    buf = io.BytesIO()
    np.save(buf, np.ascontiguousarray(a, dtype=np.float64), allow_pickle=False)
    return buf.getvalue()


def fname(seed: int, level: float) -> str:
    return f"holdout_{int(seed)}_{float(level):.1f}.npy"


def generate(seeds, levels, out, base=None) -> dict:
    """Write one `.npy` per (seed, level) and the manifest. Returns the manifest."""
    from experiments.code_state import code_state, platform_info
    seeds, levels = check_seeds(seeds), check_levels(levels)
    out = check_out(out)
    base = pp.load_base() if base is None else base
    out.mkdir(parents=True, exist_ok=True)
    files, panels = {}, []
    for seed in seeds:
        for level in levels:
            draw = pp.make_draw(base, seed, level)
            b = _npy_bytes(draw.holdout.returns)
            name = fname(seed, level)
            (out / name).write_bytes(b)
            files[name] = _sha(b)
            panels.append({"seed": seed, "level": level, "file": name, "c": draw.c,
                           "planted": [list(x) for x in draw.m_star],
                           "idx_ho_sha256": _sha(np.ascontiguousarray(
                               draw.idx_ho, dtype=np.int64).tobytes()),
                           "shape": list(draw.holdout.returns.shape)})
    manifest = {"what": "7.5 planted holdout returns, agent seeds "
                        "(prereg/planted-edge.md, build item 2)",
                "block": "design" if all(s in DESIGN for s in seeds) else "agent",
                "seeds": [min(seeds), max(seeds), len(seeds)], "levels": levels,
                "holdout_span": [pp.HO_START.isoformat(), pp.HO_END.isoformat()],
                "pinned_x_sha256": pp.PINNED_X_SHA256,
                "block_length": pp.BLOCK_LENGTH,
                "files": files, "panels": panels,
                "code_state": code_state(), "platform": platform_info(),
                "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True))
    return manifest


def seal(out) -> tuple[Path, str]:
    """A deterministic `tar.gz` of the directory, beside it. Returns (path, SHA-256)."""
    import gzip
    out = Path(out).resolve()
    names = sorted(p.name for p in out.iterdir() if p.is_file())
    if "manifest.json" not in names:
        raise SystemExit(f"{out} has no manifest.json; not a generated holdout")
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as tf:
        for n in names:
            data = (out / n).read_bytes()
            ti = tarfile.TarInfo(f"{out.name}/{n}")
            ti.size, ti.mtime, ti.mode = len(data), 0, 0o644
            ti.uid = ti.gid = 0
            ti.uname = ti.gname = ""
            tf.addfile(ti, io.BytesIO(data))
    gz = io.BytesIO()
    with gzip.GzipFile(fileobj=gz, mode="wb", mtime=0, filename="") as g:
        g.write(raw.getvalue())
    archive = out.with_name(out.name + ".tar.gz")
    archive.write_bytes(gz.getvalue())
    return archive, _sha(gz.getvalue())


def open_sealed(archive, registered_sha256: str) -> tuple[dict, dict]:
    """`(manifest, {(seed, level): returns})` from a PLAINTEXT archive, refused unless
    its SHA-256 is the registered one and every file matches the manifest."""
    b = Path(archive).read_bytes()
    got = _sha(b)
    if got != registered_sha256:
        raise SystemExit(f"{archive} has SHA-256 {got}, not the registered "
                         f"{registered_sha256}. Refused unopened.")
    members = {}
    with tarfile.open(fileobj=io.BytesIO(b), mode="r:gz") as tf:
        for m in tf.getmembers():
            if not m.isfile():
                raise SystemExit(f"{m.name}: not a regular file; refused")
            members[Path(m.name).name] = tf.extractfile(m).read()
    manifest = json.loads(members.pop("manifest.json"))
    if set(members) != set(manifest["files"]):
        raise SystemExit("the archive's files differ from its manifest's")
    out = {}
    for p in manifest["panels"]:
        data = members[p["file"]]
        if _sha(data) != manifest["files"][p["file"]]:
            raise SystemExit(f"{p['file']}: SHA-256 differs from the manifest")
        out[(int(p["seed"]), float(p["level"]))] = np.load(io.BytesIO(data),
                                                           allow_pickle=False)
    return manifest, out


def _seed_range(s: str) -> list[int]:
    a, _, b = s.partition("-")
    return list(range(int(a), int(b or a) + 1))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", required=True, help="A-B, inclusive; design block only")
    ap.add_argument("--levels", nargs="+", type=float, required=True)
    ap.add_argument("--out", required=True, help="a new directory outside the repository")
    a = ap.parse_args(argv)
    m = generate(_seed_range(a.seeds), a.levels, a.out)
    archive, sha = seal(a.out)
    print(f"{len(m['panels'])} panels ({m['block']} block) -> {archive}\n"
          f"SHA-256 {sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
