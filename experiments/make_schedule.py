"""Generate the batch schedules run_arms.sh consumes.

    python -m experiments.make_schedule            > experiments/schedule_240.txt
    python -m experiments.make_schedule --batch 3  > experiments/schedule_180.txt
    python -m experiments.make_schedule --batch 4  > experiments/schedule_80_s3.txt
    python -m experiments.make_schedule --batch 5  > experiments/schedule_80_s3_fable.txt

The default (batch 2) is documented below; batch 3 is amendment 7's arm x model
cross, batch 4 is amendment 9's s3 re-run under the recalibrated sigma, and
batch 5 is amendment 11's Fable arm at that same sigma.

Seeds 80-319, rotating across the eight blocks so every session covers every
block, with per-block counts fixed by amendment 4:

    s0 count 40; s0 budget 20 at each of B in {20, 60, 180};
    s3 control 40; s3 gate 40; s0 control 30; s0 gate 30.

A plain round robin over eight blocks would give 30 each, which is not what the
amendment specifies. The rotation therefore skips a block once its quota is
spent: the three 20-run budget blocks drop out first, and the cycle narrows
toward the end. Every block still appears in the opening cycles, which is what
"rotation across all blocks within every session" requires.
"""
from __future__ import annotations

from collections import Counter

FIRST_SEED = 80

# (config, arm, budget) in rotation order, with the quota amendment 4 fixes.
BLOCKS: list[tuple[str, str, int | None]] = [
    ("s0", "count", None),
    ("s0", "budget", 20),
    ("s0", "budget", 60),
    ("s0", "budget", 180),
    ("s3", "control", None),
    ("s3", "gate", None),
    ("s0", "control", None),
    ("s0", "gate", None),
]
QUOTA: dict[tuple[str, str, int | None], int] = {
    ("s0", "count", None): 40,
    ("s0", "budget", 20): 20,
    ("s0", "budget", 60): 20,
    ("s0", "budget", 180): 20,
    ("s3", "control", None): 40,
    ("s3", "gate", None): 40,
    ("s0", "control", None): 30,
    ("s0", "gate", None): 30,
}


def build() -> list[tuple[int, str, str, int | None]]:
    left = dict(QUOTA)
    rows: list[tuple[int, str, str, int | None]] = []
    seed = FIRST_SEED
    while sum(left.values()):
        for b in BLOCKS:
            if left[b]:
                rows.append((seed, *b))
                left[b] -= 1
                seed += 1
    return rows


def verify(rows) -> None:
    got = Counter((c, a, b) for _, c, a, b in rows)
    for b in BLOCKS:
        if got[b] != QUOTA[b]:
            raise SystemExit(f"quota mismatch for {b}: {got[b]} != {QUOTA[b]}")
    if len(rows) != sum(QUOTA.values()):
        raise SystemExit(f"row count {len(rows)} != {sum(QUOTA.values())}")
    seeds = [r[0] for r in rows]
    if seeds != list(range(FIRST_SEED, FIRST_SEED + len(rows))):
        raise SystemExit("seeds are not contiguous from FIRST_SEED")
    if len({(c, a, b) for _, c, a, b in rows[:len(BLOCKS)]}) != len(BLOCKS):
        raise SystemExit("the opening cycle does not cover every block")


# ------------------------------------------------------------- replacements
# Amendment 5. A void run keeps its row: it really was run, and deleting the row
# would shift every later line index, silently invalidating a --start on resume.
# The replacement is appended past the quota rows instead.
#
# Seed 500 rather than the next free index because 320-499 belong to batch 3;
# reusing one would put the same DGP draw in two analyses.
REPLACEMENTS: list[dict] = [
    {"void_seed": 89, "seed": 500, "config": "s0", "arm": "budget", "budget": 20,
     "why": "submission latched without a verdict (prereg AGENT_PROMPTS.md 6, amendment 5)"},
]

BATCH3_SEEDS = range(320, 500)


def replacement_rows() -> list[tuple[int, str, str, int | None]]:
    return [(r["seed"], r["config"], r["arm"], r["budget"]) for r in REPLACEMENTS]


def verify_replacements(base, reps) -> None:
    """A replacement restores the void run's cell. It may not invent a new cell,
    reuse a seed, or reach into another batch's allocation."""
    base_seeds = {row[0] for row in base}
    seen: set[int] = set()
    for spec, row in zip(REPLACEMENTS, reps):
        void = [b for b in base if b[0] == spec["void_seed"]]
        if not void:
            raise SystemExit(f"void seed {spec['void_seed']} is not in the schedule")
        if tuple(void[0][1:]) != tuple(row[1:]):
            raise SystemExit(
                f"replacement for seed {spec['void_seed']} changes the cell: "
                f"{tuple(void[0][1:])} -> {tuple(row[1:])}")
        if row[0] in base_seeds or row[0] in seen:
            raise SystemExit(f"replacement seed {row[0]} collides with an existing seed")
        if row[0] in BATCH3_SEEDS:
            raise SystemExit(f"replacement seed {row[0]} is allocated to batch 3")
        seen.add(row[0])


# ---------------------------------------------------------------- batch 3
# {control, gate, pushed} x {sonnet, fable} on s0, 30 per cell, seeds 320-499,
# registered by amendment 7.
B3_FIRST_SEED = 320
B3_PER_CELL = 30
B3_ARMS = ("control", "gate", "pushed")
B3_MODELS = ("claude-sonnet-5", "claude-fable-5-1")
B3_CELLS = [(a, m) for a in B3_ARMS for m in B3_MODELS]


def build_batch3() -> list[tuple[int, str, str, int | None, str]]:
    """Plain round robin: every cell has the same quota, so the cycle never
    narrows and each session of six consecutive runs covers all six cells."""
    rows = []
    seed = B3_FIRST_SEED
    for _ in range(B3_PER_CELL):
        for arm, model in B3_CELLS:
            rows.append((seed, "s0", arm, None, model))
            seed += 1
    return rows


def verify_batch3(rows) -> None:
    got = Counter((a, m) for _, _, a, _, m in rows)
    for cell in B3_CELLS:
        if got[cell] != B3_PER_CELL:
            raise SystemExit(f"cell {cell}: {got[cell]} != {B3_PER_CELL}")
    if len(rows) != len(B3_CELLS) * B3_PER_CELL:
        raise SystemExit(f"row count {len(rows)} != {len(B3_CELLS) * B3_PER_CELL}")
    seeds = [r[0] for r in rows]
    if seeds != list(range(B3_FIRST_SEED, B3_FIRST_SEED + len(rows))):
        raise SystemExit("seeds are not contiguous from B3_FIRST_SEED")
    if len({(a, m) for _, _, a, _, m in rows[:len(B3_CELLS)]}) != len(B3_CELLS):
        raise SystemExit("the opening cycle does not cover every cell")


# ---------------------------------------------------------------- batch 4
# s3 {control, gate} on sonnet, 40 per arm, seeds 501-580, re-run under the
# recalibrated sigma registered by amendment 9. Seeds start at 501 because 500
# is amendment 5's replacement row and 320-499 belong to batch 3; no seed is
# ever drawn twice, so no DGP draw appears in two analyses.
B4_FIRST_SEED = 501
B4_PER_ARM = 40
B4_ARMS = ("control", "gate")
B4_MODEL = "claude-sonnet-5"


def build_batch4() -> list[tuple[int, str, str, int | None, str]]:
    """Strict alternation, which is what §4 asks for in the two-arm case: no
    session can contain runs of only one arm."""
    rows = []
    seed = B4_FIRST_SEED
    for _ in range(B4_PER_ARM):
        for arm in B4_ARMS:
            rows.append((seed, "s3", arm, None, B4_MODEL))
            seed += 1
    return rows


def verify_batch4(rows) -> None:
    got = Counter(a for _, _, a, _, _ in rows)
    for arm in B4_ARMS:
        if got[arm] != B4_PER_ARM:
            raise SystemExit(f"arm {arm}: {got[arm]} != {B4_PER_ARM}")
    if len(rows) != len(B4_ARMS) * B4_PER_ARM:
        raise SystemExit(f"row count {len(rows)} != {len(B4_ARMS) * B4_PER_ARM}")
    seeds = [r[0] for r in rows]
    if seeds != list(range(B4_FIRST_SEED, B4_FIRST_SEED + len(rows))):
        raise SystemExit("seeds are not contiguous from B4_FIRST_SEED")
    # Every earlier allocation, so a batch-4 seed can never repeat a DGP draw.
    taken = set(range(FIRST_SEED, 320)) | set(BATCH3_SEEDS) | {r["seed"] for r in REPLACEMENTS}
    if taken & set(seeds):
        raise SystemExit(f"batch 4 reuses allocated seeds: {sorted(taken & set(seeds))}")
    if {a for _, _, a, _, _ in rows[:len(B4_ARMS)]} != set(B4_ARMS):
        raise SystemExit("the opening cycle does not cover every arm")


# ---------------------------------------------------------------- batch 5
# s3 {control, gate} on fable at the same recalibrated sigma batch 4 ran under,
# 40 per arm, seeds 581-660, registered by amendment 11. Batch 4 holds 501-580,
# so this starts where that ended and no DGP draw is used twice.
B5_FIRST_SEED = 581
B5_PER_ARM = 40
B5_ARMS = ("control", "gate")
B5_MODEL = "claude-fable-5-1"
B4_SEEDS = range(B4_FIRST_SEED, B4_FIRST_SEED + len(B4_ARMS) * B4_PER_ARM)


def build_batch5() -> list[tuple[int, str, str, int | None, str]]:
    """Strict alternation, as §4 requires of a two-arm batch."""
    rows = []
    seed = B5_FIRST_SEED
    for _ in range(B5_PER_ARM):
        for arm in B5_ARMS:
            rows.append((seed, "s3", arm, None, B5_MODEL))
            seed += 1
    return rows


def verify_batch5(rows) -> None:
    got = Counter(a for _, _, a, _, _ in rows)
    for arm in B5_ARMS:
        if got[arm] != B5_PER_ARM:
            raise SystemExit(f"arm {arm}: {got[arm]} != {B5_PER_ARM}")
    if len(rows) != len(B5_ARMS) * B5_PER_ARM:
        raise SystemExit(f"row count {len(rows)} != {len(B5_ARMS) * B5_PER_ARM}")
    seeds = [r[0] for r in rows]
    if seeds != list(range(B5_FIRST_SEED, B5_FIRST_SEED + len(rows))):
        raise SystemExit("seeds are not contiguous from B5_FIRST_SEED")
    if {m for _, _, _, _, m in rows} != {B5_MODEL}:
        raise SystemExit(f"batch 5 is {B5_MODEL} only")
    # Every earlier allocation, batch 4 included, so no seed is ever drawn twice.
    taken = (set(range(FIRST_SEED, 320)) | set(BATCH3_SEEDS) | set(B4_SEEDS)
             | {r["seed"] for r in REPLACEMENTS})
    if taken & set(seeds):
        raise SystemExit(f"batch 5 reuses allocated seeds: {sorted(taken & set(seeds))}")
    if {a for _, _, a, _, _ in rows[:len(B5_ARMS)]} != set(B5_ARMS):
        raise SystemExit("the opening cycle does not cover every arm")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", choices=("2", "3", "4", "5"), default="2")
    a = ap.parse_args()

    print("# seed  config  arm      budget  model")
    print("# Generated by experiments/make_schedule.py; regenerate rather than edit.")
    if a.batch == "5":
        rows5 = build_batch5()
        verify_batch5(rows5)
        print(f"# batch 5, seeds {B5_FIRST_SEED}-{B5_FIRST_SEED + len(rows5) - 1}: s3 "
              f"{B5_ARMS}, {B5_PER_ARM} per arm, {len(rows5)} rows, {B5_MODEL} at the "
              f"recalibrated s3 sigma (prereg §6, amendment 11).")
        for seed, cfg, arm, bud, model in rows5:
            print(f"{seed:<6} {cfg:<7} {arm:<8} {'-':<7} {model}")
        return
    if a.batch == "4":
        rows4 = build_batch4()
        verify_batch4(rows4)
        print(f"# batch 4, seeds {B4_FIRST_SEED}-{B4_FIRST_SEED + len(rows4) - 1}: s3 "
              f"{B4_ARMS}, {B4_PER_ARM} per arm, {len(rows4)} rows, under the "
              f"recalibrated s3 sigma (prereg §6, amendment 9).")
        for seed, cfg, arm, bud, model in rows4:
            print(f"{seed:<6} {cfg:<7} {arm:<8} {'-':<7} {model}")
        return
    if a.batch == "3":
        rows3 = build_batch3()
        verify_batch3(rows3)
        print(f"# batch 3, seeds {B3_FIRST_SEED}-{B3_FIRST_SEED + len(rows3) - 1}: "
              f"{B3_ARMS} x {B3_MODELS}, {B3_PER_CELL} per cell, {len(rows3)} rows "
              f"(prereg §6, amendment 7).")
        for seed, cfg, arm, bud, model in rows3:
            print(f"{seed:<6} {cfg:<7} {arm:<8} {'-':<7} {model}")
        return

    rows = build()
    verify(rows)
    reps = replacement_rows()
    verify_replacements(rows, reps)

    print("# amendment 4, seeds 80-319. Quotas verified against the amendment.")
    for seed, cfg, arm, bud in rows:
        print(f"{seed:<6} {cfg:<7} {arm:<8} {str(bud) if bud is not None else '-':<7} "
              f"claude-sonnet-5")
    if reps:
        print("#")
        print("# amendment 5: replacements for void runs, appended so that the line")
        print("# index of every row above is unchanged. The void row is kept.")
    for spec, (seed, cfg, arm, bud) in zip(REPLACEMENTS, reps):
        # The note goes on its own line: run_arms.sh reads the fifth field as the
        # rest of the line, so a trailing comment would become part of the model.
        print(f"# seed {seed} replaces void seed {spec['void_seed']} -- {spec['why']}")
        print(f"{seed:<6} {cfg:<7} {arm:<8} {str(bud) if bud is not None else '-':<7} "
              f"claude-sonnet-5")


if __name__ == "__main__":
    main()
