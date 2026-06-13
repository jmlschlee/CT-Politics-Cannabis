"""Town-level collectors. Fixture-driven offline; fail-loud drift in live mode.

Targeting note: the host-town list is DERIVED from cannabis-facility addresses —
we do not blind-screen every CT town.
"""
from __future__ import annotations

from ..config import config
from ..models import (
    CannabisFacility, FamilyLink, LawFirm, LegislativeOverlay, LocalEntity,
    MunicipalOfficial, VendorHypothesis,
)
from ..normalize import name_variants, parse_name
from .base import Collector, provenance_for

_FORBIDDEN = set(config().get("privacy", {}).get("forbidden_fields", []))


def _privacy_gate(source: str, d: dict) -> None:
    leaked = _FORBIDDEN.intersection(d.keys())
    if leaked:
        raise ValueError(
            f"{source}: refusing record carrying forbidden private field(s) "
            f"{sorted(leaked)} — never store home address/phone/DOB for officials "
            f"or relatives (§8)")


def _title(s: str) -> str:
    s = (s or "").strip()
    return s.title() if s.isupper() or s.islower() else s


class CannabisFacilitiesCollector(Collector):
    source_name = "cannabis_facilities"
    fixture_name = "cannabis_facilities"

    def fetch_live(self) -> list:
        """Host-town map from cannabis establishment + retail addresses. Zoning
        approval body/vote is portal-only (per-town minutes) — left blank here."""
        from .live_socrata import socrata_get
        ds = self.src["socrata"]["datasets"]
        dom = self.src["socrata"]["domain"]
        out = []
        for dsid in (ds.get("establishments"), ds.get("retail")):
            if not dsid:
                continue
            url = f"https://{dom}/d/{dsid}"
            for r in socrata_get(dom, dsid):
                op = (r.get("dba") or r.get("business") or "").strip()
                town = _title(r.get("city") or "")
                if not op or not town:
                    continue
                street = (r.get("street_address") or r.get("street") or "").strip()
                out.append({
                    "facility_id": (r.get("license") or f"{op}-{town}").strip(),
                    "operator_name": _title(op), "town": town,
                    "address": f"{_title(street)}, {town}" if street else town,
                    "license_type": (r.get("type") or "").strip(),
                    "approval_body": "", "approval_vote": "", "approval_date": "",
                    "approval_outcome": "licensed",
                    "source_url": url,
                })
        return out

    def parse(self, raw) -> list[CannabisFacility]:
        url = self.src.get("socrata", {}).get("domain", "data.ct.gov")
        out = []
        for d in raw:
            out.append(CannabisFacility(
                facility_id=d["facility_id"], operator_name=d["operator_name"],
                town=d["town"], address=d.get("address", ""),
                license_type=d.get("license_type", ""),
                approval_body=d.get("approval_body", ""),
                approval_vote=d.get("approval_vote", ""),
                approval_date=d.get("approval_date", ""),
                approval_outcome=d.get("approval_outcome", ""),
                provenance=provenance_for(self.source_name, d.get("source_url", url)),
            ))
        return out


_MUNI_PORTAL = ("per-town source (town websites / BoardDocs-CivicClerk-Granicus / "
                "assessor portals / OSE / local news) — no statewide bulk API; live "
                "collection requires per-town scraping, configured + on a per-town "
                "basis (off by default, §6). Host-town facility map IS collected live.")


class MunicipalOfficialsCollector(Collector):
    source_name = "municipal_officials"
    fixture_name = "municipal_officials"
    live_available = False
    live_unavailable_reason = _MUNI_PORTAL

    def parse(self, raw) -> list[MunicipalOfficial]:
        url = self.src.get("per_town_roster", "https://example-town.ct.gov")
        out = []
        for d in raw:
            _privacy_gate(self.source_name, d)
            out.append(MunicipalOfficial(
                person_id=d["person_id"], full_name=d["full_name"], town=d["town"],
                body=d.get("body", ""), role=d.get("role", ""),
                term_start=d.get("term_start"), term_end=d.get("term_end"),
                is_former=d.get("is_former", False),
                in_office_at=d.get("in_office_at", []),
                owns_operator_parcel=d.get("owns_operator_parcel", False),
                own_role_note=d.get("own_role_note", ""),
                name_variants=name_variants(d["full_name"]),
                provenance=provenance_for(
                    self.source_name, d.get("source_url", url)),
            ))
        return out


class FamilyLinksCollector(Collector):
    source_name = "local_news"   # family relationships are sourced from bios/news
    fixture_name = "family_links"
    live_available = False
    live_unavailable_reason = _MUNI_PORTAL

    def parse(self, raw) -> list[FamilyLink]:
        out = []
        for d in raw:
            _privacy_gate("family_links", d)
            out.append(FamilyLink(
                link_id=d["link_id"], official_name=d["official_name"],
                relative_name=d["relative_name"],
                relationship=d.get("relationship", ""),
                relative_role=d.get("relative_role", ""),
                relative_employer=d.get("relative_employer", ""),
                source_type=d.get("source_type", ""),
                is_primary_source=d.get("is_primary_source", False),
                provenance=provenance_for("family_links", d["source_url"]),
            ))
        return out


class LawFirmsCollector(Collector):
    source_name = "law_firms"
    fixture_name = "law_firms"
    live_available = False
    live_unavailable_reason = _MUNI_PORTAL

    def parse(self, raw) -> list[LawFirm]:
        url = "https://www.ctcannabischamber.org"
        out = []
        for d in raw:
            out.append(LawFirm(
                firm_id=d["firm_id"], name=d["name"],
                reps_cannabis=d.get("reps_cannabis", False),
                cannabis_clients=d.get("cannabis_clients", []),
                town_counsel_for=d.get("town_counsel_for", []),
                provenance=provenance_for(self.source_name, d.get("source_url", url)),
            ))
        return out


class LocalEntitiesCollector(Collector):
    source_name = "business_registry"   # local entities come from the registry
    fixture_name = "local_entities"
    live_available = False
    live_unavailable_reason = _MUNI_PORTAL

    def parse(self, raw) -> list[LocalEntity]:
        out = []
        for d in raw:
            out.append(LocalEntity(
                entity_id=d["entity_id"], name=d["name"], town=d.get("town", ""),
                kind=d.get("kind", ""),
                documented_operator_transactions=d.get(
                    "documented_operator_transactions", []),
                policy_excludes_cannabis=d.get("policy_excludes_cannabis", False),
                policy_note=d.get("policy_note", ""),
                provenance=provenance_for("local_entities", d["source_url"]),
            ))
        return out


class VendorHypothesesCollector(Collector):
    source_name = "local_news"
    fixture_name = "vendor_hypotheses"
    live_available = False
    live_unavailable_reason = _MUNI_PORTAL

    def parse(self, raw) -> list[VendorHypothesis]:
        out = []
        for d in raw:
            out.append(VendorHypothesis(
                hyp_id=d["hyp_id"], vendor_name=d["vendor_name"],
                operator_name=d["operator_name"], town=d.get("town", ""),
                hypothesis=d.get("hypothesis", ""),
                evidence_found=d.get("evidence_found", False),
                national_program_only=d.get("national_program_only", False),
                note=d.get("note", ""),
                provenance=provenance_for("vendor_hypotheses", d["source_url"]),
            ))
        return out


class LegislativeOverlayCollector(Collector):
    source_name = "legislators_current"   # roster + committee overlay
    fixture_name = "legislative_overlay"
    live_available = False
    live_unavailable_reason = (
        "The district->town map + committee assignments needed for the legislative "
        "overlay are not in the legislator bulk dataset; this requires CGA "
        "committee/district sources (not yet wired). Roster IS collected live.")

    def parse(self, raw) -> list[LegislativeOverlay]:
        out = []
        for d in raw:
            out.append(LegislativeOverlay(
                legislator_name=d["legislator_name"], chamber=d.get("chamber"),
                district=str(d.get("district", "")),
                towns_represented=d.get("towns_represented", []),
                committee=d.get("committee", ""), employer=d.get("employer", ""),
                financial_stake=d.get("financial_stake", "none"),
                is_former=d.get("is_former", False),
                provenance=provenance_for("legislative_overlay", d["source_url"]),
            ))
        return out


class MeetingMinutesCollector(Collector):
    """Returns raw minute records for the vote/recusal parser (analyze.municipal)."""
    source_name = "meeting_minutes"
    fixture_name = "meeting_minutes"
    live_available = False
    live_unavailable_reason = _MUNI_PORTAL

    def parse(self, raw) -> list[dict]:
        return list(raw)


class CannabisZoningCollector(Collector):
    """Per-town cannabis zoning status (Approved / Prohibited / Moratorium) — the
    municipal cannabis policy-action layer. Live on data.ct.gov."""
    source_name = "cannabis_zoning"
    fixture_name = "cannabis_zoning"

    def fetch_live(self) -> list:
        from .live_socrata import socrata_get
        sc = self.src["socrata"]
        url = f"https://{sc['domain']}/d/{sc['dataset_id']}"
        out = []
        for r in socrata_get(sc["domain"], sc["dataset_id"]):
            town = (r.get("town") or "").strip()
            status = (r.get("status") or "").strip()
            if not town:
                continue
            out.append({"town": town, "status": status or "Unspecified",
                        "source_url": url})
        return out

    def parse(self, raw) -> list[dict]:
        return list(raw)
