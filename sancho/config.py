"""Sancho's levers, in one config file (`sancho/config.json`, documented in sancho/CONFIG.md).

The default is the registered version-2 configuration. `load()` returns it; `load(path)` reads
another. Every Config carries the SHA-256 of its canonical JSON, and whether it is the default.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent / "config.json"
NON_DEFAULT_LINE = ("sancho: non-default configuration {short}. The registered results apply to the "
                    "default only; every configuration tried on the same data is another strategy and "
                    "must be declared as such.")


def canonical(values: dict) -> str:
    return json.dumps(values, sort_keys=True, separators=(",", ":"))


def sha256_of(values: dict) -> str:
    return hashlib.sha256(canonical(values).encode()).hexdigest()


@dataclass(frozen=True)
class Config:
    values: dict
    sha256: str
    is_default: bool
    path: str

    def notice(self) -> str | None:
        """The one line a non-default config prints; None for the default."""
        return None if self.is_default else NON_DEFAULT_LINE.format(short=self.sha256[:12])


def _default_values() -> dict:
    return json.loads(DEFAULT_PATH.read_text())


def load(path: str | Path | None = None) -> Config:
    p = Path(path) if path is not None else DEFAULT_PATH
    values = json.loads(Path(p).read_text())
    missing = sorted(set(_default_values()) - set(values))
    if missing:
        raise ValueError(f"{p}: missing levers {missing} (copy sancho/config.json and edit it)")
    sha = sha256_of(values)
    return Config(values=values, sha256=sha, is_default=sha == sha256_of(_default_values()), path=str(p))
