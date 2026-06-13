"""DCP cannabis licenses AND individual credentials (backer + key employee).

The individual-credential rosters are MANDATORY: a prior manual pass missed an
active Key Employee credential because only business/backer ownership lists were
checked. This collector yields both cannabis ENTITIES and cannabis PERSONS, and
the key-employee/backer rosters feed the person table directly.
"""
from __future__ import annotations

from ..models import CannabisEntity, CannabisPerson
from .base import Collector, provenance_for


class DCPCannabisCollector(Collector):
    source_name = "dcp_cannabis"
    fixture_name = "dcp_cannabis"

    def fetch_live(self) -> dict:
        """Business-level cannabis licenses from data.ct.gov. The INDIVIDUAL
        backer/key-employee credentials are portal-only (eLicense roster) and are
        NOT pulled here — that layer is reported as a coverage gap."""
        from .live_socrata import socrata_get
        ds = self.src["socrata"]["datasets"]
        dom = self.src["socrata"]["domain"]
        entities = []
        for key, dsid in (("establishments", ds.get("cannabis_establishments")),
                          ("retail", ds.get("cannabis_retail"))):
            if not dsid or dsid.startswith("PORTAL_ONLY"):
                continue
            url = f"https://{dom}/d/{dsid}"
            for r in socrata_get(dom, dsid):
                name = (r.get("business") or r.get("dba") or "").strip()
                if not name:
                    continue
                entities.append({
                    "entity_id": (r.get("license") or name).strip(),
                    "name": name,
                    "entity_type": (r.get("type") or "").strip(),
                    "license_type": (r.get("type") or "").strip(),
                    "status": "Active",
                    "source_url": url,
                })
        return {"entities": entities, "persons": []}

    def parse(self, raw) -> list:
        url = self.src.get("elicense_roster", {}).get(
            "base_url", "https://www.elicense.ct.gov")
        out: list = []
        for d in raw.get("entities", []):
            out.append(CannabisEntity(
                entity_id=d["entity_id"], name=d["name"],
                entity_type=d.get("entity_type", ""),
                license_type=d.get("license_type", ""),
                status=d.get("status", ""),
                provenance=provenance_for(self.source_name, d.get("source_url", url)),
            ))
        for d in raw.get("persons", []):
            out.append(CannabisPerson(
                cp_id=d["cp_id"], full_name=d["full_name"],
                role=d.get("role", ""),
                credential_type=d.get("credential_type", ""),
                entity_name=d.get("entity_name", ""),
                source_kind="dcp",
                provenance=provenance_for(self.source_name, d.get("source_url", url)),
            ))
        return out

    def split(self, records: list) -> tuple[list[CannabisEntity], list[CannabisPerson]]:
        ents = [r for r in records if isinstance(r, CannabisEntity)]
        pers = [r for r in records if isinstance(r, CannabisPerson)]
        return ents, pers
