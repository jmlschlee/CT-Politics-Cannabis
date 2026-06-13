"""CT Office of State Ethics — cannabis lobbyist analysis.

Unlike the legacy fixture-only `lobbyists.LobbyistsCollector`, this is a LIVE
collector. OSE publishes the registered lobbyist *communicators* as a data.ct.gov
Socrata dataset (`4ixq-tnwe`, current 2025-2026 biennium) with each communicator's
name, the ORGANIZATION they lobby for, city, registration date, and member type.

We flag CANNABIS lobbying two ways:
  1. organization_name matches the shared cannabis term markers (is_cannabis_text),
     e.g. "CT Cannabis Chamber of Commerce", "Budr Cannabis"; or
  2. organization_name matches a known CT cannabis operator/brand that doesn't carry
     the word "cannabis" (curated markers + any names passed in from the registry).

COVERAGE LIMIT (flagged honestly in-report): this dataset is the In-House / business-
organization communicator roster for the CURRENT biennium. CONTRACT lobbying firms
that lobby FOR a cannabis client (the client→firm registrations) live on the OSE
eLobbyist portal, not this bulk dataset, so a contract lobbyist hired by a cannabis
company is NOT captured here unless their org itself is cannabis-named.
"""
from __future__ import annotations

import re

from ..analyze.cannabis_terms import is_cannabis_text
from ..models import Lobbyist, Provenance

_DATASET = "4ixq-tnwe"
_DOMAIN = "data.ct.gov"
_SRC = f"https://{_DOMAIN}/d/{_DATASET}"

# Known CT cannabis operators/brands/coalitions whose NAME omits "cannabis" but is
# unmistakably cannabis-industry (extends is_cannabis_text for the lobbyist roster).
CANNABIS_OPERATOR_MARKERS = [
    "curaleaf", "acreage", "fine fettle", "theraplant", "ctpharma", "ct pharma",
    "verano", "zen leaf", "affinity", "still river", "nautilus", "budr",
    "the botanist", "advanced grow", "willow brook", "rino", "fueled",
    "sweetspot", "nuera", "green leaf", "marijuana policy project",
]


def _is_cannabis_org(name: str, extra_markers: list[str]) -> bool:
    if not name:
        return False
    if is_cannabis_text(name):
        return True
    low = name.lower()
    return any(m and m in low for m in CANNABIS_OPERATOR_MARKERS) or \
        any(m and m in low for m in extra_markers)


class OseLobbyistCollector:
    """Pull the OSE communicator roster and isolate cannabis-industry lobbyists."""

    def __init__(self, *, offline: bool = False, refresh: bool = False):
        self.offline = offline
        self.refresh = refresh
        self.last_status = ("", 0, "")
        self.total_communicators = 0

    def _fixture_rows(self) -> list[dict]:
        from ..config import ROOT
        import json
        fx = ROOT / "tests" / "fixtures" / "ose_lobbyists.json"
        return json.loads(fx.read_text()) if fx.exists() else []

    def collect(self, extra_markers: list[str] | None = None) -> list[Lobbyist]:
        markers = [m.lower() for m in (extra_markers or []) if m and len(m) >= 5]
        prov = Provenance(source_name="ose_lobbyists", source_url=_SRC)
        out: list[Lobbyist] = []
        if self.offline:
            rows = self._fixture_rows()
            self.total_communicators = len(rows)
            for r in rows:
                out.append(self._to_model(r, prov))
            self.last_status = ("fixture", len(out),
                                "OSE communicators is live-only; offline uses fixture")
            return out
        try:
            from .live_socrata import socrata_get
            rows = socrata_get(_DOMAIN, _DATASET, page_size=2000)
        except Exception as e:  # noqa: BLE001
            self.last_status = ("unavailable", 0, f"OSE dataset fetch failed: {e}")
            return out
        self.total_communicators = len(rows)
        for r in rows:
            org = (r.get("organization_name") or "").strip()
            if not _is_cannabis_org(org, markers):
                continue
            out.append(self._to_model(r, prov))
        self.last_status = (
            "live", len(out),
            f"{len(rows)} OSE communicators scanned; {len(out)} cannabis-industry")
        return out

    def _to_model(self, r: dict, prov: Provenance) -> Lobbyist:
        first = (r.get("first_name") or "").strip()
        last = (r.get("last_name") or "").strip()
        full = re.sub(r"\s+", " ", f"{first} {last}").strip()
        org = (r.get("organization_name") or "").strip()
        yr = None
        m = re.search(r"(\d{4})", r.get("register_date") or "")
        if m:
            yr = int(m.group(1))
        return Lobbyist(
            lobbyist_id=f"ose::{full}::{org}".lower(),
            communicator_name=full, client_name=org, is_cannabis=True,
            registration_year=yr, hometown=(r.get("city") or "").strip().title(),
            provenance=prov)
