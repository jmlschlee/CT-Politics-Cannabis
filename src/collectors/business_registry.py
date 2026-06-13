"""CT Secretary of the State business registry ("CONCORD" LLC screen).

Bulk Open-Data file is strongly preferred. Playwright scraping of the interactive
UI is a fallback that stays OFF unless both sources.yaml allow_scrape AND
config.yaml scrape.globally_enabled are true (and ToS/robots permit it).

Yields cannabis ENTITIES and their principals/agents/organizers as cannabis
PERSONS (only for entities whose name/purpose reads as cannabis-related).
"""
from __future__ import annotations

from ..analyze.cannabis_terms import is_cannabis_text
from ..models import CannabisEntity, CannabisPerson
from .base import Collector, provenance_for


class BusinessRegistryCollector(Collector):
    source_name = "business_registry"
    fixture_name = "business_registry"
    live_available = False
    live_unavailable_reason = (
        "CT Secretary of the State business search has no public bulk API; live "
        "collection of principals/agents requires Playwright scraping of the "
        "interactive UI (off by default until ToS/robots reviewed, §6).")

    def parse(self, raw) -> list:
        url = self.src.get("business_search", {}).get(
            "base_url", "https://business.ct.gov")
        out: list = []
        for d in raw:
            name = d["entity_name"]
            cannabis = d.get("is_cannabis")
            if cannabis is None:
                cannabis = is_cannabis_text(name) or is_cannabis_text(d.get("purpose", ""))
            if not cannabis:
                continue  # only cannabis-related entities are in scope
            out.append(CannabisEntity(
                entity_id=d["entity_id"], name=name,
                entity_type=d.get("entity_type", "LLC"),
                status=d.get("status", ""),
                provenance=provenance_for(self.source_name, d.get("source_url", url)),
            ))
            for pr in d.get("principals", []):
                out.append(CannabisPerson(
                    cp_id=f"{d['entity_id']}::{pr['name']}::{pr.get('role','')}",
                    full_name=pr["name"], role=pr.get("role", "principal"),
                    credential_type="business-principal", entity_name=name,
                    source_kind="business",
                    provenance=provenance_for(self.source_name, d.get("source_url", url)),
                ))
        return out
