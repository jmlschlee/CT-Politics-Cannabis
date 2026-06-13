"""Municipal-layer orchestration: collect town data -> target host towns ->
classify each (town, operator) into the four-class dossier (§4.1).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .analyze.municipal import TownDossier, classify_facility, parse_minutes
from .collectors.municipal import (
    CannabisFacilitiesCollector, CannabisZoningCollector, FamilyLinksCollector,
    LawFirmsCollector, LegislativeOverlayCollector, LocalEntitiesCollector,
    MeetingMinutesCollector, MunicipalOfficialsCollector, VendorHypothesesCollector,
)
from .models import TownConnection


@dataclass
class MunicipalResult:
    dossiers: list[TownDossier] = field(default_factory=list)
    connections: list[TownConnection] = field(default_factory=list)
    review_rows: list[dict] = field(default_factory=list)
    counts: dict = field(default_factory=dict)
    host_towns: list[str] = field(default_factory=list)
    coverage: dict = field(default_factory=dict)
    zoning: list = field(default_factory=list)
    known_findings: list = field(default_factory=list)
    town_attorney_findings: list = field(default_factory=list)  # firm cannabis chains
    host_town_roster: list = field(default_factory=list)        # every host town
    official_tie_findings: list = field(default_factory=list)   # Glassman-category leads


class MunicipalPipeline:
    def __init__(self, offline: bool = True, refresh: bool = False):
        self.offline = offline
        self.refresh = refresh

    def _run(self, label: str, cls):
        c = cls(offline=self.offline, refresh=self.refresh)
        rows = c.collect()
        self.coverage[label] = {"status": c.last_status[0],
                                "count": c.last_status[1], "note": c.last_status[2]}
        return rows

    def collect(self) -> dict:
        self.coverage: dict = {}
        return dict(
            facilities=self._run("Cannabis facility -> town map", CannabisFacilitiesCollector),
            officials=self._run("Municipal officials", MunicipalOfficialsCollector),
            family_links=self._run("Family links (officials)", FamilyLinksCollector),
            firms=self._run("Town counsel / law firms", LawFirmsCollector),
            local_entities=self._run("Local entities (vendors)", LocalEntitiesCollector),
            vendors=self._run("Vendor hypotheses", VendorHypothesesCollector),
            overlays=self._run("Legislative overlay", LegislativeOverlayCollector),
            minutes_raw=self._run("Meeting minutes", MeetingMinutesCollector),
            zoning=self._run("Cannabis zoning (town status)", CannabisZoningCollector),
        )

    def run(self) -> MunicipalResult:
        data = self.collect()
        minutes = parse_minutes(data["minutes_raw"])
        dossiers: list[TownDossier] = []
        for fac in data["facilities"]:
            dossiers.append(classify_facility(
                facility=fac, officials=data["officials"],
                family_links=data["family_links"], firms=data["firms"],
                vendors=data["vendors"], overlays=data["overlays"], minutes=minutes,
            ))

        connections = [c for d in dossiers for c in d.connections]
        review_rows = []
        for c in connections:
            if c.review_gated or not c.publishable or c.classification == "UNCONFIRMED":
                review_rows.append(dict(
                    town=c.town, operator=c.operator, subject=c.subject_name,
                    subject_kind=c.subject_kind, connection_type=c.connection_type,
                    classification=c.classification, confidence=c.confidence,
                    is_private_individual=c.is_private_individual,
                    substantial_conflict=c.substantial_conflict,
                    explanation=c.explanation,
                    source_url="; ".join(c.citations),
                ))

        counts = dict(
            host_towns=len({d.town for d in dossiers}),
            facilities=len(data["facilities"]),
            officials=len(data["officials"]),
            connections=len(connections),
            confirmed=sum(1 for c in connections if c.classification == "CONFIRMED"),
            unconfirmed=sum(1 for c in connections if c.classification == "UNCONFIRMED"),
            unsupported=sum(1 for c in connections if c.classification == "UNSUPPORTED"),
            context=sum(1 for c in connections if c.classification == "CONTEXT"),
            substantial_conflicts=sum(1 for c in connections if c.substantial_conflict),
            municipal_review_queue=len(review_rows),
            zoning_towns=len(data.get("zoning", [])),
            zoning_moratorium=sum(1 for z in data.get("zoning", [])
                                  if "morator" in (z.get("status") or "").lower()),
            zoning_prohibited=sum(1 for z in data.get("zoning", [])
                                  if "prohibit" in (z.get("status") or "").lower()),
        )
        # Documented municipal cannabis connections (curated, sourced; e.g. the
        # Simsbury First Selectman -> Pullman & Comley cannabis-attorney -> Curaleaf
        # case). These are real public-record findings for the Municipal section.
        known = []
        try:
            import json
            from .config import ROOT
            kp = ROOT / "data" / "known_municipal_findings.json"
            if kp.exists():
                known = json.loads(kp.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            known = []

        # ---- MUNICIPAL EXPANSION (V2 #4): host-town roster + town-attorney chains ----
        # (a) ALL host towns with their operator(s) and zoning status (not just the
        #     towns that have a documented connection).
        zoning_by_town = {(z.get("town") or "").lower(): z.get("status", "")
                          for z in data.get("zoning", [])}
        roster_map: dict[str, dict] = {}
        for d in dossiers:
            g = roster_map.setdefault(d.town, dict(
                town=d.town, operators=set(),
                zoning=zoning_by_town.get((d.town or "").lower(), "")))
            if d.operator:
                g["operators"].add(d.operator)
        host_town_roster = [dict(town=g["town"], operators=sorted(g["operators"]),
                                 zoning=g["zoning"], counsel="", cannabis_counsel=False)
                            for g in roster_map.values()]
        host_town_roster.sort(key=lambda g: g["town"].lower())

        # (b) town-attorney cannabis chains: the SOURCED firm→town assignments, plus a
        #     bounded LIVE web-discovery of each host town's counsel (cannabis firms
        #     only; never fabricated).
        town_attorney_findings = []
        official_tie_findings = []
        try:
            from .collectors.town_attorneys import TownAttorneyChains
            tac = TownAttorneyChains(offline=self.offline)
            seen_towns = set()
            for f in tac.sourced_findings():
                town_attorney_findings.append(f)
                seen_towns.add((f["town"] or "").lower())
            if not self.offline:
                # Generalize BOTH halves of the Glassman category to EVERY host town:
                # (a) town counsel that is a cannabis-practice firm, and (b) a town
                # official/family directly tied to cannabis. Budget covers all towns.
                BUDGET = max(60, len(host_town_roster) + 5)
                for g in host_town_roster:
                    if BUDGET <= 0:
                        break
                    if (g["town"] or "").lower() not in seen_towns:
                        BUDGET -= 1
                        hit = tac.discover_town_counsel(g["town"], budget_ok=True)
                        if hit:
                            town_attorney_findings.append(hit)
                            seen_towns.add((g["town"] or "").lower())
                    if BUDGET <= 0:
                        break
                    BUDGET -= 1
                    ot = tac.discover_official_tie(g["town"], budget_ok=True)
                    if ot:
                        official_tie_findings.append(ot)
            # annotate the roster with any cannabis-counsel finding
            ta_by_town = {(f["town"] or "").lower(): f for f in town_attorney_findings}
            for g in host_town_roster:
                f = ta_by_town.get((g["town"] or "").lower())
                if f:
                    g["counsel"] = f["firm"]
                    g["cannabis_counsel"] = True
            self.coverage["Town-attorney cannabis chains"] = {
                "status": ("live" if not self.offline else "fixture"),
                "count": len(town_attorney_findings),
                "note": (f"{len(town_attorney_findings)} host town(s) whose town counsel "
                         f"is a cannabis-practice firm (sourced + web-discovered). Town-"
                         f"counsel assignments are not bulk-published; unlisted host "
                         f"towns' counsel were not identified this run (INCOMPLETE).")}
        except Exception:  # noqa: BLE001
            town_attorney_findings = []
        counts["host_town_roster"] = len(host_town_roster)
        counts["town_attorney_chains"] = len(town_attorney_findings)
        counts["official_tie_leads"] = len(official_tie_findings)

        return MunicipalResult(
            dossiers=dossiers, connections=connections, review_rows=review_rows,
            counts=counts, host_towns=sorted({d.town for d in dossiers}),
            coverage=getattr(self, "coverage", {}),
            zoning=data.get("zoning", []), known_findings=known,
            town_attorney_findings=town_attorney_findings,
            host_town_roster=host_town_roster,
            official_tie_findings=official_tie_findings,
        )
