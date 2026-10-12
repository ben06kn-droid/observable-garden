"""Writes examples/data/tiny_panel.npz: a small synthetic daily panel (600 rows, 12 assets,
8 features) with a weak edge planted in one feature. The committed file is the object of record;
rerunning this writes the same arrays (the .npz container itself carries a timestamp).

    python -m examples.make_tiny_panel
"""
from pathlib import Path

from quixote import panel

OUT = Path(__file__).resolve().parent / "data" / "tiny_panel.npz"


def main() -> None:
    sha = panel.save(OUT, **panel.tiny(seed=7))
    print(f"wrote {OUT} (sha256 {sha[:16]})")


if __name__ == "__main__":
    main()
