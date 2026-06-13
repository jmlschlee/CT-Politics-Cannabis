"""Verified-resolution cache.

Once a (legislator <-> cannabis person/business) relationship has been resolved,
its verdict (tier + evidence + sources) is cached and COMPACTED so later runs reuse
it instantly instead of re-running the expensive web resolution. Confirmed
credentials therefore make every subsequent analysis faster.

Keyed by canonical (official, cannabis person, business). `--refresh-cache` forces
re-verification.
"""
from __future__ import annotations

import json

from ..config import cache_dir
from ..normalize import canonical

_PATH = cache_dir() / "verified_resolutions.json"
# Bump when the resolution LOGIC changes (e.g. tighter false-positive filters) so
# stale verdicts auto-invalidate instead of being reused.
RESOLVER_VERSION = 3


def vkey(official: str, cannabis_person: str, entity: str) -> str:
    return f"{canonical(official)}::{canonical(cannabis_person)}::{canonical(entity)}"


def load_verified() -> dict:
    if _PATH.exists():
        try:
            data = json.loads(_PATH.read_text(encoding="utf-8"))
            if data.get("_version") != RESOLVER_VERSION:
                return {}   # resolver logic changed -> discard stale verdicts
            return {k: v for k, v in data.items() if k != "_version"}
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_verified(cache: dict) -> None:
    # compact: drop empty fields to keep the file small / fast to load
    compact = {"_version": RESOLVER_VERSION}
    for k, v in cache.items():
        if k == "_version":
            continue
        compact[k] = {kk: vv for kk, vv in v.items() if vv not in (None, [], "")}
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(compact, separators=(",", ":"), indent=0),
                     encoding="utf-8")
