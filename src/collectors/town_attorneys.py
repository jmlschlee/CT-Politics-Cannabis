"""Town-attorney cannabis-client chains (municipal expansion, V2 #4).

CT towns rarely have an in-house lawyer; they retain a private firm as town
counsel / corporation counsel. Several of the firms that do this municipal work
ALSO run a cannabis practice and represent cannabis operators — the documented
Simsbury / Pullman & Comley / Andrew Glassman / Curaleaf case is the template.
When the same firm advises a host town AND represents cannabis interests, that is
an appearance concern for cannabis matters before that town.

This module:
  * loads the SOURCED firm registry (data/town_attorney_chains.json) — firms with a
    documented cannabis practice, plus any town-counsel assignments we can source;
  * `sourced_findings()` emits the assignments we can stand behind;
  * `discover_town_counsel()` (LIVE, bounded) web-searches a host town's counsel and,
    only if the named firm matches a cannabis-practice firm, returns a finding — it
    NEVER fabricates a town↔firm link.
"""
from __future__ import annotations

import json
import re

from ..config import ROOT


def _load_registry() -> list[dict]:
    p = ROOT / "data" / "town_attorney_chains.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("firms", [])
    except Exception:  # noqa: BLE001
        return []


def _firm_key(firm: str) -> str:
    """A distinctive, matchable fragment of a firm name (drop the entity suffix)."""
    f = re.sub(r"[^a-z0-9 &]", " ", (firm or "").lower())
    f = re.sub(r"\b(llp|llc|p\.?c\.?|pc|law|offices?|the)\b", " ", f)
    # drop stray single letters left by punctuation (e.g. "p c" from "P.C.")
    f = " ".join(t for t in f.split() if t == "&" or len(t) > 1)
    return re.sub(r"\s+", " ", f).strip()


# Keywords that confirm a page is actually about a town's LEGAL COUNSEL (not just a
# page that happens to mention a firm). Required for a web-discovered assignment.
_COUNSEL_CTX = re.compile(
    r"town attorney|corporation counsel|town counsel|city attorney|"
    r"legal counsel|retained|represents the town|serves as counsel", re.I)


class TownAttorneyChains:
    def __init__(self, *, offline: bool = False):
        self.offline = offline
        self.firms = _load_registry()
        self._keys = [(_firm_key(f["firm"]), f) for f in self.firms]
        self.searched: list[str] = []

    def match_firm(self, text: str):
        """Return the registry firm whose distinctive name appears in `text`."""
        low = (text or "").lower()
        for key, firm in self._keys:
            # match on the firm's lead surname-ish token(s) to avoid over-broad hits
            head = key.split(" and ")[0].split(" & ")[0].strip()
            if head and head in low:
                return firm
        return None

    def sourced_findings(self) -> list[dict]:
        """Town-counsel assignments we can source (firm advises town AND is cannabis)."""
        out = []
        for f in self.firms:
            for town in f.get("towns_advised", []):
                out.append(dict(
                    town=town, firm=f["firm"],
                    cannabis_practice=f.get("cannabis_practice", ""),
                    cannabis_lead=f.get("cannabis_lead", ""),
                    sources=f.get("sources", []), discovered=False))
        return out

    def discover_official_tie(self, town: str, *, budget_ok: bool = True):
        """LIVE generalization of the Simsbury/Glassman CATEGORY to any host town: a
        town official (or their family) tied to cannabis. Conservative — only returns a
        POSSIBLE lead when a credible result names a town-leadership ROLE together with
        a cannabis term and a relationship/own-stake cue. Never fabricates."""
        if self.offline or not budget_ok:
            return None
        try:
            from ..resolve.web_search import web_search
        except Exception:  # noqa: BLE001
            return None
        role_re = re.compile(r"first selectman|selectwoman|\bmayor\b|town manager|"
                             r"town council|planning and zoning|p&z|board of selectmen|"
                             r"town attorney|corporation counsel|economic development",
                             re.I)
        canna_re = re.compile(r"cannabis|marijuana|dispensar|cultivat", re.I)
        rel_re = re.compile(r"spouse|husband|wife|son|daughter|brother|sister|family|"
                            r"owner|backer|stake|invest|consult|attorney for|"
                            r"represent|client|sited|siting|host", re.I)
        for q in (f"{town} CT first selectman mayor cannabis",
                  f"{town} Connecticut town official cannabis dispensary conflict"):
            self.searched.append(q)
            for r in web_search(q, max_results=6, offline=False):
                blob = f"{r.title} {r.text}"
                if (role_re.search(blob) and canna_re.search(blob)
                        and rel_re.search(blob)):
                    return dict(
                        town=town, headline=r.title.strip(),
                        snippet=r.text[:220].strip(), source=r.url, discovered=True)
        return None

    def discover_town_counsel(self, town: str, *, budget_ok: bool = True):
        """LIVE: identify a host town's counsel firm and, if it is a cannabis-practice
        firm in the registry, return a finding. Returns None if offline, over budget,
        or no cannabis-firm match (never fabricates)."""
        if self.offline or not budget_ok:
            return None
        try:
            from ..resolve.web_search import web_search
        except Exception:  # noqa: BLE001
            return None
        for q in (f"{town} CT town attorney corporation counsel",
                  f"{town} Connecticut town counsel law firm"):
            self.searched.append(q)
            for r in web_search(q, max_results=6, offline=False):
                blob = f"{r.title} {r.text}"
                firm = self.match_firm(blob)
                # require BOTH the firm name AND a town-counsel context in the SAME
                # result — a loose mention of the firm is not proof it is the counsel.
                if firm and _COUNSEL_CTX.search(blob):
                    return dict(
                        town=town, firm=firm["firm"],
                        cannabis_practice=firm.get("cannabis_practice", ""),
                        cannabis_lead=firm.get("cannabis_lead", ""),
                        sources=[r.url] + firm.get("sources", []),
                        discovered=True)
        return None
