"""SEEC campaign-finance receipts. Contributions are matched against a
cannabis-donor dictionary built from DCP license-holders, their
owners/executives, cannabis PACs, and registered cannabis lobbyists."""
from __future__ import annotations

from ..models import Contribution
from .base import Collector, provenance_for


class CampaignFinanceCollector(Collector):
    source_name = "campaign_finance"
    fixture_name = "campaign_finance"
    live_available = False
    live_unavailable_reason = (
        "CT campaign finance (SEEC eCRIS) has no public Socrata bulk API; live "
        "collection requires the eCRIS portal/export (scraping, off by default).")

    def parse(self, raw) -> list[Contribution]:
        url = self.src.get("seec_ecris", {}).get("base_url", "https://seec.ct.gov")
        out: list[Contribution] = []
        for d in raw:
            out.append(Contribution(
                contrib_id=d["contrib_id"],
                contributor_name=d["contributor_name"],
                employer=d.get("employer", ""),
                occupation=d.get("occupation", ""),
                amount=float(d.get("amount", 0) or 0),
                date=d.get("date", ""),
                recipient_committee=d.get("recipient_committee", ""),
                provenance=provenance_for(self.source_name, d.get("source_url", url)),
            ))
        return out
