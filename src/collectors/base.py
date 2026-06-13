"""Shared collector machinery: provenance, on-disk caching, polite HTTP with
retries + per-host throttle, fixture loading, and source-drift detection.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..config import ROOT, cache_dir, config, source, user_agent
from ..models import Provenance

FIXTURE_DIR = ROOT / "tests" / "fixtures"


class SourceDriftError(RuntimeError):
    """Raised when a live source no longer matches the shape recorded in
    sources.yaml. Names the source and its verified_on date so a human can fix
    the config rather than the pipeline silently emitting wrong data."""

    def __init__(self, source_name: str, detail: str):
        s = source(source_name)
        super().__init__(
            f"SOURCE DRIFT in '{source_name}' (verified_on="
            f"{s.get('verified_on', '?')}): {detail}. "
            f"Re-verify the live source and update sources.yaml before re-running."
        )
        self.source_name = source_name


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def provenance_for(source_name: str, url: str, snippet: str | None = None) -> Provenance:
    return Provenance(source_name=source_name, source_url=url, raw_snippet=snippet)


def load_fixture(name: str) -> Any:
    """Load tests/fixtures/<name>.json (the offline corpus)."""
    path = FIXTURE_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Fixture not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


class Collector:
    """Base collector. Subclasses set `source_name` and implement
    `parse(raw) -> list[model]` and `fetch_live() -> raw`.

    `collect()` honours offline mode (cache/fixture only, zero live hits) and
    caches every live payload so a warm re-run does no network I/O.
    """

    source_name: str = ""
    fixture_name: str = ""
    # Portal-only sources (no public bulk API; live collection needs scraping which
    # is off by default) set this False so a LIVE run skips them gracefully and the
    # report flags the coverage gap, rather than crashing the whole run.
    live_available: bool = True
    live_unavailable_reason: str = ""

    def __init__(self, offline: bool = True, refresh: bool = False):
        self.offline = offline
        self.refresh = refresh
        self.cfg = config()
        self._last_host_hit: dict[str, float] = {}
        # Coverage breadcrumb the pipeline reads after collect():
        #   ('fixture'|'cache'|'live'|'unavailable'|'disabled', count, note)
        self.last_status: tuple[str, int, str] = ("", 0, "")

    # -- config helpers ---------------------------------------------------
    @property
    def src(self) -> dict:
        return source(self.source_name)

    @property
    def enabled(self) -> bool:
        return bool(self.src.get("enabled", False))

    @property
    def allow_scrape(self) -> bool:
        return bool(self.src.get("allow_scrape", False)) and \
            bool(self.cfg.get("scrape", {}).get("globally_enabled", False))

    # -- caching ----------------------------------------------------------
    def _cache_path(self, key: str) -> Path:
        # Include the collector CLASS so collectors that share a source_name (e.g.
        # several reuse 'local_news'/'legislators_current') never collide on cache.
        ident = f"{type(self).__name__}:{self.source_name}:{key}"
        h = hashlib.sha256(ident.encode()).hexdigest()[:24]
        return cache_dir() / f"{type(self).__name__}.{h}.json"

    def cache_read(self, key: str) -> Optional[Any]:
        path = self._cache_path(key)
        if not path.exists():
            return None
        ttl = self.cfg.get("cache", {}).get("ttl_days", 30)
        if not self.offline and not self.cfg.get("cache", {}).get("respect_on_offline", True):
            pass
        if self.refresh and not self.offline:
            age_days = (time.time() - path.stat().st_mtime) / 86400
            if age_days > ttl:
                return None
        return json.loads(path.read_text(encoding="utf-8"))

    def cache_write(self, key: str, payload: Any) -> None:
        self._cache_path(key).write_text(
            json.dumps(payload, ensure_ascii=False, indent=0), encoding="utf-8"
        )

    # -- polite HTTP ------------------------------------------------------
    def _throttle(self, host: str) -> None:
        delay = self.cfg.get("http", {}).get("per_host_delay_seconds", 2.0)
        last = self._last_host_hit.get(host, 0.0)
        wait = delay - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        self._last_host_hit[host] = time.time()

    def http_get(self, url: str, params: dict | None = None) -> str:
        """Live GET — only reachable when offline=False. Politeness + retries."""
        if self.offline:
            raise RuntimeError(
                f"{self.source_name}: offline mode — refusing live request to {url}"
            )
        import httpx  # local import so offline runs need no network stack
        from urllib.parse import urlparse

        host = urlparse(url).netloc
        max_retries = self.cfg.get("http", {}).get("max_retries", 4)
        timeout = self.cfg.get("http", {}).get("timeout_seconds", 30)
        headers = {"User-Agent": user_agent()}
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            self._throttle(host)
            try:
                resp = httpx.get(url, params=params, headers=headers, timeout=timeout)
                resp.raise_for_status()
                return resp.text
            except Exception as e:  # noqa: BLE001
                last_exc = e
                time.sleep(min(2 ** attempt, 10))
        raise RuntimeError(f"{self.source_name}: GET {url} failed after "
                           f"{max_retries} attempts: {last_exc}")

    # -- overridable ------------------------------------------------------
    def fetch_live(self) -> Any:
        raise SourceDriftError(
            self.source_name,
            "live collector not yet wired — run `python -m src.cli verify-sources` "
            "to confirm the current dataset id / export path, then implement fetch_live()",
        )

    def parse(self, raw: Any) -> list:
        raise NotImplementedError

    def collect(self) -> list:
        if not self.enabled:
            self.last_status = ("disabled", 0, "source disabled in sources.yaml")
            return []
        if self.offline:
            # Offline = the deterministic bundled demo corpus. Prefer the FIXTURE so
            # results never depend on a live cache left over from a prior live run;
            # fall back to cache only when no fixture exists.
            raw = load_fixture(self.fixture_name) if self.fixture_name else None
            status = "fixture"
            if raw is None:
                raw = self.cache_read("primary")
                status = "cache"
            if raw is None:
                self.last_status = ("fixture", 0, "no fixture/cache")
                return []
            out = self.parse(raw)
            self.last_status = (status, len(out), "")
            return out
        # live path
        if not self.live_available:
            self.last_status = ("unavailable", 0, self.live_unavailable_reason or
                                "no public bulk API; live collection requires scraping "
                                "(disabled by default, §6)")
            return []
        raw = self.cache_read("primary")
        status = "cache"
        if raw is None or self.refresh:
            raw = self.fetch_live()
            self.cache_write("primary", raw)
            status = "live"
        out = self.parse(raw)
        self.last_status = (status, len(out), "")
        return out
