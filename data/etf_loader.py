"""6.5's in-sample loader, and the refusals that keep the holdout out of reach.

The panel loader proper is part of the real-data sandbox. What is here is the
part that must exist before any loading does: the checks that make touching the
holdout an error rather than a mistake.

Three refusals, all hard:

1. **Sealed archives.** Any path whose suffix is `.enc`, `.gpg` or `.asc` is
   refused unopened. The encrypted second copy of the holdout is one of these,
   and its passphrase is not on this machine.
2. **Quarantined directories.** Any path under `~/Desktop`, where that copy
   lives.
3. **Holdout dates.** Any row on or after 2023-01-01 in a file this loader
   opens. The in-sample export should contain none; if one appears, the file is
   wrong and loading stops rather than filtering it away.

`prereg/agent-on-real-data.md` registers all three.
"""
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

HOLDOUT_START = dt.date(2023, 1, 1)
SEALED_SUFFIXES = (".enc", ".gpg", ".asc")
QUARANTINED = (Path.home() / "Desktop",)
INSAMPLE_DIR = Path(__file__).resolve().parent / "raw" / "etf_insample"


class HoldoutRefused(RuntimeError):
    """Raised instead of reading anything that could be, or contain, the holdout."""


def refuse_sealed_or_quarantined(path: str | Path) -> Path:
    """The check every read goes through. Returns the path, or raises."""
    p = Path(path).expanduser()
    resolved = p.resolve() if p.exists() else p.absolute()
    if resolved.suffix.lower() in SEALED_SUFFIXES:
        raise HoldoutRefused(
            f"{resolved.name} is a sealed archive ({resolved.suffix}); it is the encrypted "
            "holdout copy and is never opened here. Its passphrase is not on this machine.")
    for q in QUARANTINED:
        if resolved == q or q in resolved.parents:
            raise HoldoutRefused(
                f"{resolved} is under {q}, where the sealed holdout copy lives; nothing there "
                "is read by this loader.")
    return resolved


def load_insample(path: str | Path) -> tuple[list[dt.date], list[float], list[float]]:
    """One exported in-sample file: (dates, adjusted closes, volumes).

    Refuses a sealed or quarantined path, and refuses the file outright if any
    row falls on or after the holdout's first date.
    """
    p = refuse_sealed_or_quarantined(path)
    dates: list[dt.date] = []
    adj: list[float] = []
    vol: list[float] = []
    with p.open(newline="") as fh:
        for row in csv.DictReader(fh):
            d = dt.date.fromisoformat(row["date"])
            if d >= HOLDOUT_START:
                raise HoldoutRefused(
                    f"{p.name} contains {d.isoformat()}, on or after the holdout's first date "
                    f"{HOLDOUT_START.isoformat()}. The in-sample export must not; this file is "
                    "wrong and nothing is loaded from it.")
            dates.append(d)
            adj.append(float(row["adjclose"]))
            vol.append(float(row["volume"]))
    return dates, adj, vol


def load_panel(directory: str | Path = INSAMPLE_DIR) -> dict[str, tuple]:
    d = refuse_sealed_or_quarantined(directory)
    return {p.stem: load_insample(p) for p in sorted(d.glob("*.csv"))}
