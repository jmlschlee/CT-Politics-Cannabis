"""Load and expose sources.yaml + config.yaml. No endpoint is ever hard-coded in
logic — collectors read everything from here."""
from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent


@functools.lru_cache(maxsize=None)
def _load(name: str) -> dict[str, Any]:
    path = ROOT / name
    if not path.exists():
        raise FileNotFoundError(f"Missing config file: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{name} must parse to a mapping, got {type(data).__name__}")
    return data


def sources() -> dict[str, Any]:
    return _load("sources.yaml")


def config() -> dict[str, Any]:
    return _load("config.yaml")


def source(name: str) -> dict[str, Any]:
    """Return the config block for one source, erroring clearly if absent."""
    s = sources()
    if name not in s:
        raise KeyError(
            f"Source '{name}' not defined in sources.yaml. "
            f"Available: {sorted(k for k in s if k != 'meta')}"
        )
    return s[name]


def out_dir() -> Path:
    d = ROOT / config().get("output", {}).get("dir", "out")
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_dir() -> Path:
    d = ROOT / config().get("cache", {}).get("dir", "data/cache")
    d.mkdir(parents=True, exist_ok=True)
    return d


def contact() -> str:
    return sources().get("meta", {}).get("contact", "unknown@example.org")


def user_agent() -> str:
    tmpl = config().get("http", {}).get("user_agent_template", "ct-cannabis-conflicts")
    return tmpl.format(contact=contact())
