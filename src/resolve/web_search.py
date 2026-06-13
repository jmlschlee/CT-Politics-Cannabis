"""Reproducible web search from the program itself (DuckDuckGo HTML), with on-disk
caching. Used by the relationship-resolution engine to ACTIVELY verify whether a
surname lead reflects a real relationship — never stopping at 'same surname'."""
from __future__ import annotations

import hashlib
import html
import json
import re
import time
from dataclasses import dataclass

from ..config import cache_dir

_UA = "Mozilla/5.0 (compatible; ct-cannabis-conflicts/0.1; public-interest research)"
_SNIPPET = re.compile(
    r'result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?result__snippet[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL)
_TAG = re.compile(r"<[^>]+>")


@dataclass
class WebResult:
    title: str
    url: str
    snippet: str

    @property
    def text(self) -> str:
        return f"{self.title} {self.snippet}"


def _clean(s: str) -> str:
    return html.unescape(_TAG.sub("", s or "")).strip()


def _cache_path(query: str):
    h = hashlib.sha256(("ddg:" + query).encode()).hexdigest()[:24]
    d = cache_dir() / "websearch"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{h}.json"


def web_search(query: str, *, max_results: int = 6, offline: bool = False,
               delay: float = 0.4) -> list[WebResult]:
    """DuckDuckGo HTML search. Cached; offline returns cache-only. On any failure
    returns [] (the caller records that the search was attempted but yielded nothing)."""
    cp = _cache_path(query)
    if cp.exists():
        try:
            return [WebResult(**r) for r in json.loads(cp.read_text())][:max_results]
        except Exception:  # noqa: BLE001
            pass
    if offline:
        return []
    try:
        import httpx
        time.sleep(delay)
        resp = httpx.post("https://html.duckduckgo.com/html/", data={"q": query},
                          headers={"User-Agent": _UA}, timeout=20, follow_redirects=True)
        resp.raise_for_status()
        out: list[WebResult] = []
        for m in _SNIPPET.finditer(resp.text):
            url = html.unescape(m.group(1))
            # DDG wraps external links in a redirect; pull the real target.
            rm = re.search(r"uddg=([^&]+)", url)
            if rm:
                from urllib.parse import unquote
                url = unquote(rm.group(1))
            out.append(WebResult(title=_clean(m.group(2)), url=url,
                                 snippet=_clean(m.group(3))))
            if len(out) >= max_results:
                break
        cp.write_text(json.dumps([r.__dict__ for r in out]), encoding="utf-8")
        return out
    except Exception:  # noqa: BLE001
        return []
