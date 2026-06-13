"""Minimal Socrata (data.ct.gov) reader with paging + politeness, used by the
live collectors. Read-only GET against public Open-Data endpoints."""
from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlencode

from ..config import config, user_agent


def socrata_get(domain: str, dataset_id: str, *, select: str | None = None,
                where: str | None = None, order: str | None = None,
                page_size: int = 5000, max_rows: int | None = None,
                _delay: float | None = None) -> list[dict]:
    """Fetch rows from a Socrata dataset, paging via $limit/$offset.

    Honors the per-host delay from config.yaml so we never hammer the portal.
    `_delay` overrides it (e.g. faster for the robust data.ct.gov registry bulk
    reads). Raises with a clear message (the caller wraps drift handling)."""
    import httpx

    base = f"https://{domain}/resource/{dataset_id}.json"
    delay = _delay if _delay is not None else \
        config().get("http", {}).get("per_host_delay_seconds", 2.0)
    timeout = config().get("http", {}).get("timeout_seconds", 30)
    headers = {"User-Agent": user_agent()}
    rows: list[dict] = []
    offset = 0
    while True:
        params: dict[str, Any] = {"$limit": page_size, "$offset": offset}
        if select:
            params["$select"] = select
        if where:
            params["$where"] = where
        if order:
            params["$order"] = order
        url = f"{base}?{urlencode(params)}"
        resp = httpx.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        batch = resp.json()
        if isinstance(batch, dict) and batch.get("error"):
            raise RuntimeError(f"Socrata error for {dataset_id}: {batch.get('message')}")
        if not batch:
            break
        rows.extend(batch)
        offset += page_size
        if max_rows and len(rows) >= max_rows:
            return rows[:max_rows]
        if len(batch) < page_size:
            break
        time.sleep(delay)
    return rows
