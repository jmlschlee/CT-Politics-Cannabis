"""Statements of Financial Interests — the ONLY legitimate source that confirms a
spouse/family cannabis-employment tie. SENSITIVE: store ONLY the cannabis-relevant
fields (legislator name, year, spouse employer, associated business). Never a home
address, phone, DOB, or non-cannabis family detail (enforced here + in models)."""
from __future__ import annotations

from ..config import config
from ..models import SFIFiling
from .base import Collector, provenance_for

_FORBIDDEN = set(config().get("privacy", {}).get("forbidden_fields", []))


class EthicsSFICollector(Collector):
    source_name = "ethics_sfi"
    fixture_name = "ethics_sfi"
    live_available = False
    live_unavailable_reason = (
        "Statements of Financial Interests are obtained via the Office of State "
        "Ethics portal/FOIA, not a bulk API; this is the only source that confirms "
        "a spouse/family cannabis-employment tie, so that layer is a coverage gap "
        "in a bulk-only live run.")

    def parse(self, raw) -> list[SFIFiling]:
        url = self.src.get("office_of_state_ethics", {}).get(
            "base_url", "https://www.ethics.ct.gov")
        out: list[SFIFiling] = []
        for d in raw:
            # Defensive privacy gate: refuse if a forbidden field leaked into the feed.
            leaked = _FORBIDDEN.intersection(d.keys())
            if leaked:
                raise ValueError(
                    f"ethics_sfi: refusing record carrying forbidden private "
                    f"field(s) {sorted(leaked)} — fix the upstream parser")
            out.append(SFIFiling(
                filing_id=d["filing_id"],
                legislator_name=d["legislator_name"],
                filing_year=d.get("filing_year"),
                spouse_employer=d.get("spouse_employer", ""),
                associated_business=d.get("associated_business", ""),
                provenance=provenance_for(self.source_name, d.get("source_url", url)),
            ))
        return out
