"""Orchestration: collect -> store -> resolve -> classify -> report.

Idempotent and offline-capable: with `offline=True` no live request is made;
all data comes from the cache or the bundled fixture corpus.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .analyze import classify_match, parse_recusals
from .collectors.business_registry import BusinessRegistryCollector
from .collectors.campaign_finance import CampaignFinanceCollector
from .collectors.dcp_cannabis import DCPCannabisCollector
from .collectors.ethics_sfi import EthicsSFICollector
from .collectors.legislators_current import LegislatorsCurrentCollector
from .collectors.legislators_historical import LegislatorsHistoricalCollector
from .collectors.lobbyists import LobbyistsCollector
from .config import config
from .donor_dict import build_donor_dict
from .models import (
    CannabisEntity, CannabisPerson, Contribution, Finding, Legislator, Lobbyist,
    Match, SFIFiling,
)
from .normalize import canonical
from .analyze.cannabis_terms import is_cannabis_text
from .resolve import Matcher, RefRecord
from .store import Store

# Committee-name noise to strip when recovering a candidate name.
_COMMITTEE_NOISE = re.compile(
    r"\b(friends of|committee to elect|citizens for|the committee|"
    r"committee for|exploratory committee|re-?elect|leadership pac|pac|"
    r"committee|for state (?:senate|representative)|for|inc)\b",
    re.IGNORECASE,
)


def candidate_from_committee(committee: str) -> str:
    name = _COMMITTEE_NOISE.sub(" ", committee or "")
    name = re.sub(r"\s+", " ", name).strip(" -")
    return name


@dataclass
class PipelineResult:
    legislators: list[Legislator] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    recusals: list = field(default_factory=list)
    review_rows: list[dict] = field(default_factory=list)
    counts: dict = field(default_factory=dict)
    db_path: str = ""
    coverage: dict = field(default_factory=dict)
    mode: str = "OFFLINE"
    network: object = None          # cannabis ownership NetworkResult (live)
    cannabis_persons: list = field(default_factory=list)
    entities: list = field(default_factory=list)
    legislator_cannabis_leads: list = field(default_factory=list)
    campaign_finance: dict = field(default_factory=dict)  # SEEC eCRIS contributions
    lobbying: dict = field(default_factory=dict)           # OSE cannabis lobbyists


class Pipeline:
    def __init__(self, offline: bool = True, refresh: bool = False,
                 since_year: Optional[int] = None, sources_filter: Optional[set] = None):
        self.offline = offline
        self.refresh = refresh
        self.cfg = config()
        self.since_year = since_year or self.cfg["run"].get("default_since_year", 2010)
        self.sources_filter = sources_filter  # None => all
        self.matcher = Matcher(self.cfg)

    def _use(self, name: str) -> bool:
        return self.sources_filter is None or name in self.sources_filter

    def _mk(self, cls):
        return cls(offline=self.offline, refresh=self.refresh)

    # -- collect ----------------------------------------------------------
    def _run(self, label: str, cls):
        """Run a collector, recording its coverage breadcrumb for the report."""
        c = cls(offline=self.offline, refresh=self.refresh)
        rows = c.collect()
        self.coverage[label] = {"status": c.last_status[0],
                                "count": c.last_status[1],
                                "note": c.last_status[2]}
        return rows

    def collect(self):
        self.coverage: dict = {}
        legs: list[Legislator] = []
        if self._use("legislators_current"):
            legs += self._run("Legislators (current+historical)", LegislatorsCurrentCollector)
        if self._use("legislators_historical"):
            legs += self._run("Legislators (historical, merged)", LegislatorsHistoricalCollector)

        dcp_records = self._run("DCP cannabis licenses", DCPCannabisCollector) if self._use("dcp_cannabis") else []
        dcp_entities = [r for r in dcp_records if isinstance(r, CannabisEntity)]
        dcp_persons = [r for r in dcp_records if isinstance(r, CannabisPerson)]

        # Business registry OWNERSHIP NETWORK: resolve cannabis LLCs -> principals/
        # agents -> recursively to real PEOPLE. This is what turns the facility list
        # into an influence map. Live only (the registry has no offline fixture).
        biz_persons: list = []
        self.network = None
        if self._use("business_registry"):
            if self.offline:
                biz_records = self._run("Business registry principals", BusinessRegistryCollector)
                biz_persons = [r for r in biz_records if isinstance(r, CannabisPerson)]
                dcp_entities += [r for r in biz_records if isinstance(r, CannabisEntity)]
                self.coverage["Cannabis ownership network (registry)"] = {
                    "status": "fixture", "count": len(biz_persons), "note": ""}
            else:
                from .collectors.ownership_network import resolve_cannabis_network
                from datetime import date as _date
                names = [e.name for e in dcp_entities]
                lic_map = {e.name: (e.license_type, e.entity_id) for e in dcp_entities}
                self.network = resolve_cannabis_network(
                    names, max_depth=3, license_map=lic_map,
                    retrieved_date=_date.today().isoformat())
                biz_persons = self.network.persons
                note = ""
                if self.network.unmatched_entities:
                    note = (f"{len(self.network.unmatched_entities)} of "
                            f"{len(names)} cannabis businesses had no exact "
                            f"Business-Registry name match (INCOMPLETE — needs fuzzy "
                            f"/ DBA / filing-history resolution)")
                self.coverage["Cannabis ownership network (registry principals/agents)"] = {
                    "status": "live" if self.network.queried else "unavailable",
                    "count": len(biz_persons),
                    "note": note or self.network.note}
        biz_entities = []

        # DCP eLicense INDIVIDUAL credentials: Establishment Backers + Key Employees,
        # scraped from the eLicense roster (names tied directly to each cannabis
        # license, with city + dates). The richest individual-credential source.
        elic_persons: list = []
        if self._use("dcp_cannabis"):
            from .collectors.elicense_roster import ELicenseRosterScraper
            scraper = ELicenseRosterScraper(offline=self.offline, refresh=self.refresh)
            elic_persons = scraper.collect()
            self.coverage["DCP eLicense credentials (backers, key employees)"] = {
                "status": scraper.last_status[0], "count": scraper.last_status[1],
                "note": scraper.last_status[2]}
        biz_persons = list(biz_persons) + elic_persons

        lobbyists: list[Lobbyist] = self._run("Lobbyists", LobbyistsCollector) if self._use("lobbyists") else []
        contribs: list[Contribution] = self._run("Campaign finance", CampaignFinanceCollector) if self._use("campaign_finance") else []
        sfi: list[SFIFiling] = self._run("Statements of Financial Interests", EthicsSFICollector) if self._use("ethics_sfi") else []

        return dict(
            legislators=legs,
            entities=dcp_entities + biz_entities,
            cannabis_persons=dcp_persons + biz_persons,
            lobbyists=lobbyists, contributions=contribs, sfi=sfi,
        )

    # -- build reference records to match against legislators -------------
    def build_refs(self, data: dict):
        refs: list[RefRecord] = []
        amounts: dict[str, float] = {}

        # 1) DCP credentials + business principals — the legislator as a stakeholder
        for cp in data["cannabis_persons"]:
            ref_type = "dcp" if cp.source_kind == "dcp" else "business"
            label = (f"{cp.credential_type or cp.role} @ "
                     f"{cp.entity_name or '(entity)'}")
            refs.append(RefRecord(
                ref_type=ref_type, ref_id=cp.cp_id, label=label,
                name=cp.full_name, employer=cp.entity_name,
                extra={"source_url": cp.provenance.source_url},
            ))

        # 2) Cannabis donations — recipient committee -> legislator
        dd = build_donor_dict(data["entities"], data["cannabis_persons"], data["lobbyists"])
        for c in data["contributions"]:
            is_can, why = dd.is_cannabis_contribution(c)
            if not is_can:
                continue
            cand = candidate_from_committee(c.recipient_committee)
            label = (f"${c.amount:.0f} from {c.contributor_name}"
                     f"{' / ' + c.employer if c.employer else ''} "
                     f"to {c.recipient_committee} [{why}]")
            refs.append(RefRecord(
                ref_type="donation", ref_id=c.contrib_id, label=label,
                name=cand or c.recipient_committee, employer="",
                extra={"source_url": c.provenance.source_url},
            ))
            amounts[c.contrib_id] = c.amount

        # 3) Cannabis lobbyists as possible RELATIVES (family lead -> review)
        for lob in data["lobbyists"]:
            if not lob.is_cannabis:
                continue
            refs.append(RefRecord(
                ref_type="lobbyist", ref_id=lob.lobbyist_id,
                label=f"registered cannabis lobbyist (client {lob.client_name})",
                name=lob.communicator_name,
                hometown=lob.hometown,
                is_family_candidate=True,
                extra={"source_url": lob.provenance.source_url},
            ))

        # 4) SFI spouse/family employer that is a cannabis business -> confirmed lead
        sfi_confirm: set[str] = set()
        for f in data["sfi"]:
            emp = f.spouse_employer or f.associated_business
            is_can, _ = dd.is_cannabis_contribution(
                Contribution(contrib_id="x", contributor_name=emp, employer=emp,
                             provenance=f.provenance))
            if not (is_can or is_cannabis_text(emp)):
                continue
            ref_id = f.filing_id
            refs.append(RefRecord(
                ref_type="sfi", ref_id=ref_id,
                label=f"SFI {f.filing_year}: spouse/family employer '{emp}'",
                name=f.legislator_name,
                # The member filed this themselves — identity is certain (authoritative),
                # and it CONCERNS family, but is not an uncertain relative-identity guess.
                concerns_family=True, authoritative_identity=True,
                extra={"source_url": f.provenance.source_url},
            ))
            sfi_confirm.add(ref_id)
        return refs, amounts, sfi_confirm

    _CONCORD_STOP = {
        "llc", "inc", "corp", "co", "ltd", "lp", "llp", "the", "and", "of",
        "cannabis", "marijuana", "dispensary", "cultivation", "cultivators",
        "micro", "retailer", "retail", "hybrid", "holdings", "ventures", "group",
        "wellness", "company", "enterprises", "management", "partners", "labs",
        "farms", "farm", "brands", "naturals", "organics", "remedies", "health",
        "medical", "care", "green", "leaf", "house", "garden", "gardens", "ct",
        "connecticut", "new", "east", "west", "north", "south", "valley", "river",
    }

    def _concord_screen(self, legislators, entities):
        """Honest fallback when no principal/owner roster is bulk-available: surface
        a legislator whose DISTINCTIVE surname appears as a token in a cannabis
        business name, as a low-confidence REVIEW lead (a surname inside an LLC name
        is NOT proof of involvement — verify identity). Returns (matches, refs)."""
        from .normalize import surname_key
        by_surname: dict[str, list] = {}
        for leg in legislators:
            by_surname.setdefault(surname_key(leg.full_name), []).append(leg)
        matches: list[Match] = []
        refs: list[RefRecord] = []
        seen: set[tuple] = set()
        for e in entities:
            toks = {t for t in canonical(e.name).split()
                    if len(t) >= 5 and t not in self._CONCORD_STOP and not t.isdigit()}
            for t in toks:
                for leg in by_surname.get(t, []):
                    key = (leg.person_id, e.entity_id, t)
                    if key in seen:
                        continue
                    seen.add(key)
                    ref_id = f"concord::{e.entity_id}::{t}"
                    label = (f"surname '{t}' appears in cannabis business "
                             f"'{e.name}'" + (f" ({e.entity_type})" if e.entity_type else ""))
                    refs.append(RefRecord(
                        ref_type="business", ref_id=ref_id, label=label, name=e.name,
                        employer=e.name,
                        extra={"source_url": e.provenance.source_url}))
                    matches.append(Match(
                        person_id=leg.person_id, ref_type="business", ref_id=ref_id,
                        ref_label=label, confidence="POSSIBLE/REVIEW",
                        explanation=(f"CONCORD name screen — legislator surname '{t}' "
                                     f"appears in cannabis business name '{e.name}'. "
                                     f"No principal/owner roster is bulk-available, so "
                                     f"this is a low-confidence lead; verify identity "
                                     f"before treating as a connection."),
                        score=0.0, is_family_lead=False))
        return matches, refs

    def _legislator_cannabis_leads(self, screenable, cannabis_persons) -> list[dict]:
        """Surface cannabis PRINCIPALS/AGENTS who SHARE A SURNAME with a (cannabis-era)
        legislator. A shared surname is a LEAD — the official themselves, a relative,
        or a coincidence — never a finding without primary-source verification."""
        from rapidfuzz import fuzz
        from .normalize import surname_key, canonical, parse_name
        leg_url = (screenable[0].provenance.source_url if screenable else "")
        by_surname: dict[str, list] = {}
        for leg in screenable:
            by_surname.setdefault(surname_key(leg.full_name), []).append(leg)
        common = self.matcher.high_collision
        leads: list[dict] = []
        seen: set[tuple] = set()
        for p in cannabis_persons:
            sk = surname_key(p.full_name)
            for leg in by_surname.get(sk, []):
                # dedup by (legislator, cannabis PERSON) — a person backing several
                # businesses must not produce duplicate leads
                key = (leg.person_id, canonical(p.full_name))
                if key in seen:
                    continue
                seen.add(key)
                sim = fuzz.token_sort_ratio(canonical(p.full_name),
                                            canonical(leg.full_name))
                lf = canonical(parse_name(leg.full_name).first)
                pf = canonical(parse_name(p.full_name).first)
                same_first = bool(lf and pf and (lf == pf or lf[0] == pf[0]
                                                 or lf in pf or pf in lf))
                # PUBLIC-ADDRESS DOUBLE-CHECK: does the cannabis principal's residence
                # (or business) town match the legislator's hometown? This is the
                # strongest cheap accuracy signal for same-person / relative.
                leg_town = canonical(leg.hometown)
                p_res, p_biz = canonical(p.residence_city), canonical(p.business_city)
                town_match = bool(leg_town and (leg_town == p_res or leg_town == p_biz))
                town_known = bool(p_res or p_biz)
                if same_first and town_match:
                    conf, kind = "PROBABLE", ("given name AND town both match — likely the "
                                              "same person; verify")
                elif sim >= 90 and same_first:
                    conf, kind = "PROBABLE", "name strongly matches — likely the same person or close relative"
                elif town_match:
                    conf, kind = "POSSIBLE/REVIEW", ("surname + SAME TOWN — elevated lead "
                                                     "(relative or self); verify")
                elif same_first:
                    conf, kind = "POSSIBLE/REVIEW", "given name also aligns — possible self or relative"
                elif town_known and not town_match:
                    conf, kind = "POSSIBLE/REVIEW", (f"surname only; residence town "
                        f"'{p.residence_city or p.business_city}' differs from official's "
                        f"'{leg.hometown}' — likely NOT the same person")
                else:
                    conf, kind = "POSSIBLE/REVIEW", "surname only — could be a relative or a coincidence"
                if sk in common and conf == "PROBABLE" and not town_match:
                    conf = "POSSIBLE/REVIEW"  # common-surname guard (unless town corroborates)
                role = ("State Senator" if leg.chamber == "Senate"
                        else "State Representative" if leg.chamber == "House" else "Legislator")
                leads.append(dict(
                    person=leg.full_name, role=role + (" (former)" if leg.is_former else ""),
                    district_or_town=leg.hometown or leg.district, party=leg.party,
                    years_served=leg.years_served, is_former=leg.is_former,
                    cannabis_person=p.full_name, cannabis_entity=p.entity_name,
                    cannabis_role=p.role, dcp_or_filing=p.license_type or p.credential_type,
                    license_number=p.license_number,
                    cannabis_residence=p.residence_city, cannabis_biz_city=p.business_city,
                    record_date=p.registration_date, retrieved_date=p.retrieved_date,
                    town_match=town_match,
                    confidence=conf, name_similarity=int(sim), same_first=same_first,
                    is_common_surname=sk in common,
                    source_urls=[u for u in (p.provenance.source_url, p.business_url, leg_url) if u],
                    explanation=(
                        f"Cannabis {p.role} '{p.full_name}'"
                        f"{' (residence ' + p.residence_city + ')' if p.residence_city else ''} "
                        f"of cannabis business '{p.entity_name}'"
                        f"{' [' + p.license_type + ']' if p.license_type else ''} shares the "
                        f"surname '{sk}' with {role} {leg.full_name} ({leg.party}, "
                        f"{leg.hometown}; served {leg.years_served}). {kind.capitalize()}. "
                        f"VERIFY against a primary source (SFI spouse field, campaign bio, "
                        f"registry residence/officer match) before treating as a connection."),
                ))
        leads.sort(key=lambda d: (not d["town_match"], d["confidence"] != "PROBABLE",
                                  d["is_common_surname"], -d["name_similarity"]))
        return leads

    def _campaign_finance(self, screenable, cannabis_persons, leads, entities) -> dict:
        """SEEC eCRIS pass: pull cannabis-linked campaign contributions and tie each
        legislative-recipient one to a specific legislator (by committee surname +
        district). Runs in both modes — offline uses the bundled fixture."""
        from .collectors.seec_finance import SeecCampaignFinance, is_legislative
        from .normalize import surname_key, canonical

        biz = [p.entity_name for p in cannabis_persons if getattr(p, "entity_name", "")]
        biz += [e.name for e in entities if getattr(e, "name", "")]
        persons: list[str] = []
        for d in leads:
            if d.get("person"):
                persons.append(d["person"])
            if d.get("cannabis_person"):
                persons.append(d["cannabis_person"])

        coll = SeecCampaignFinance(offline=self.offline, refresh=self.refresh)
        contribs = coll.collect(biz, persons)
        self._seec_status = coll.last_status

        # Index cannabis-era legislators by surname for committee->legislator linkage.
        leg_by_surname: dict[str, list] = {}
        for l in screenable:
            leg_by_surname.setdefault(surname_key(l.full_name), []).append(l)

        def _link_legislator(committee: str, district: str):
            """Match a recipient committee to a cannabis-era legislator. Committee
            names are typically 'Lastname YEAR' or 'Lastname for Office', so we test
            every word in the committee name against the legislator-surname index."""
            cand = candidate_from_committee(committee)
            tokens = re.findall(r"[A-Za-z]{3,}", f"{cand} {committee}")
            found: list = []
            seen_ids = set()
            for tok in tokens:
                # index keys are canonical surnames; compare each committee word
                # directly (surname_key expects a full name and drops a lone token).
                for l in leg_by_surname.get(canonical(tok), []):
                    if l.person_id not in seen_ids:
                        seen_ids.add(l.person_id)
                        found.append(l)
            if len(found) == 1:
                return found[0]
            if len(found) > 1 and district:
                return next((l for l in found
                             if str(l.district).strip() == str(district).strip()), None)
            return None

        rows: list[dict] = []
        for c in contribs:
            if not is_legislative(c):
                continue  # only STATE LEGISLATIVE recipients are findings here
            leg = _link_legislator(c.recipient_committee, c.district)
            rows.append(dict(
                donor=c.contributor_name, employer=c.employer,
                occupation=c.occupation, city=c.city, amount=c.amount, date=c.date,
                committee=c.recipient_committee, office=c.office_sought,
                district=c.district, party=c.party, year=c.election_year,
                matched_by=c.matched_by, source_url=c.provenance.source_url,
                legislator=(leg.full_name if leg else ""),
                legislator_party=(leg.party if leg else ""),
                is_former=(leg.is_former if leg else False)))

        # Group by recipient (a matched legislator, else the committee name).
        groups: dict[str, dict] = {}
        for r in rows:
            key = r["legislator"] or f"[committee] {r['committee']}"
            g = groups.setdefault(key, dict(
                recipient=key, legislator=r["legislator"], office=r["office"],
                district=r["district"], party=r["legislator_party"] or r["party"],
                total=0.0, n=0, donors=set(), employers=set(),
                sources=set(), years=set()))
            g["total"] += r["amount"] or 0.0
            g["n"] += 1
            g["donors"].add(r["donor"])
            if r["employer"]:
                g["employers"].add(r["employer"])
            if r["source_url"]:
                g["sources"].add(r["source_url"])
            if r["year"]:
                g["years"].add(r["year"])
        by_recipient = []
        for g in groups.values():
            by_recipient.append(dict(
                recipient=g["recipient"], legislator=g["legislator"],
                office=g["office"], district=g["district"], party=g["party"],
                total=round(g["total"], 2), n=g["n"],
                donors=sorted(g["donors"]), employers=sorted(g["employers"]),
                years=sorted(g["years"]), sources=sorted(g["sources"])))
        by_recipient.sort(key=lambda g: (-g["total"], g["recipient"]))

        leg_total = round(sum(r["amount"] or 0.0 for r in rows), 2)
        return dict(
            rows=rows, by_recipient=by_recipient,
            legislative_count=len(rows), legislative_total=leg_total,
            all_count=len(contribs),
            linked_legislators=sorted({r["legislator"] for r in rows if r["legislator"]}),
            status=coll.last_status, capped=coll.capped,
            searches=getattr(coll.driver, "searches", []))

    def _lobbyist_analysis(self, screenable, cannabis_persons, entities) -> dict:
        """OSE pass: pull the cannabis-industry lobbyist roster and flag any
        communicator who surname-matches a cannabis-era legislator (a legislator or
        relative registered to lobby for cannabis). Offline uses the fixture."""
        from .collectors.ose_lobbyists import OseLobbyistCollector
        from .normalize import surname_key, canonical, parse_name

        markers = [getattr(e, "name", "") for e in entities]
        markers += [getattr(p, "entity_name", "") for p in cannabis_persons]
        coll = OseLobbyistCollector(offline=self.offline, refresh=self.refresh)
        lobbyists = coll.collect(markers)

        # roster grouped by organization
        from collections import OrderedDict
        orgs: "OrderedDict[str, dict]" = OrderedDict()
        for lb in lobbyists:
            g = orgs.setdefault(lb.client_name, dict(
                organization=lb.client_name, communicators=[], cities=set(),
                years=set(), source=lb.provenance.source_url))
            g["communicators"].append(lb.communicator_name)
            if lb.hometown:
                g["cities"].add(lb.hometown)
            if lb.registration_year:
                g["years"].add(str(lb.registration_year))
        roster = [dict(organization=g["organization"],
                       communicators=sorted(set(g["communicators"])),
                       cities=sorted(g["cities"]), years=sorted(g["years"]),
                       source=g["source"]) for g in orgs.values()]
        roster.sort(key=lambda g: g["organization"].lower())

        # surname cross-reference to cannabis-era legislators
        leg_by_surname: dict[str, list] = {}
        for l in screenable:
            leg_by_surname.setdefault(surname_key(l.full_name), []).append(l)
        matches = []
        for lb in lobbyists:
            sk = surname_key(lb.communicator_name)
            for l in leg_by_surname.get(sk, []):
                same = canonical(lb.communicator_name) == canonical(l.full_name)
                same_first = (canonical(parse_name(lb.communicator_name).first) ==
                              canonical(parse_name(l.full_name).first))
                note = ("the legislator is THEMSELVES a registered cannabis lobbyist"
                        if same else
                        "shares first AND last name — likely the legislator or a close "
                        "relative; VERIFY" if same_first else
                        "shares a surname — possible relative or coincidence; VERIFY")
                matches.append(dict(
                    legislator=l.full_name, party=l.party,
                    district=l.district, is_former=l.is_former,
                    communicator=lb.communicator_name, organization=lb.client_name,
                    same_person=same, same_first=same_first, note=note,
                    source=lb.provenance.source_url))
        matches.sort(key=lambda m: (not m["same_person"], not m["same_first"]))

        return dict(
            roster=roster, legislator_matches=matches,
            cannabis_lobbyist_count=len(lobbyists), org_count=len(roster),
            total_communicators=coll.total_communicators,
            status=coll.last_status)

    def _cannabis_era(self, leg: Legislator) -> bool:
        """A legislator is in-scope for CROSS-REFERENCING only if their service could
        overlap the CT cannabis industry. CT legalized MEDICAL cannabis in 2012
        (PA 12-55) and ADULT-USE in 2021 (RERACA), so `since_year` defaults to 2012;
        a member who left office before then cannot have a cannabis conflict. The
        full historical roster (back to 1915 in the source dataset) is still
        collected/stored/in the tracker — it is just excluded from matching."""
        if not leg.is_former:
            return True
        years = [int(y) for y in re.findall(r"\b(1[89]\d\d|20\d\d)\b", leg.years_served)]
        if not years:
            return True  # unknown tenure — keep (can't safely exclude)
        return max(years) >= self.since_year

    # -- run --------------------------------------------------------------
    def run(self, db_path: Optional[str] = None) -> PipelineResult:
        data = self.collect()
        refs, amounts, sfi_confirm = self.build_refs(data)
        legs = data["legislators"]
        leg_by_id = {l.person_id: l for l in legs}
        # Scope cross-referencing to cannabis-era legislators (full roster still stored).
        screenable = [l for l in legs if self._cannabis_era(l)]

        matches = self.matcher.match_all(screenable, refs)

        # CONCORD surname-in-business-name screen (fallback for unresolved entities)
        concord_matches, concord_refs = self._concord_screen(screenable, data["entities"])
        matches += concord_matches
        refs += concord_refs

        # Legislator <-> cannabis principal/agent surname leads (the influence map).
        legislator_cannabis_leads = self._legislator_cannabis_leads(
            screenable, data["cannabis_persons"])

        # RELATIONSHIP RESOLUTION: a surname match is only a lead. Actively try to
        # resolve each one from public sources (web: news/bios/company pages) and
        # reclassify into CONFIRMED / PROBABLE / POSSIBLE / SURNAME ONLY. Live only
        # (offline keeps the surname-based confidence; web_search is cache/empty there).
        if not self.offline and legislator_cannabis_leads:
            from .resolve.relationship import resolve_relationship
            from .resolve.verified_cache import load_verified, save_verified, vkey
            from datetime import date as _date
            _TIER_RANK = {"CONFIRMED": 0, "PROBABLE": 1, "POSSIBLE": 2,
                          "SURNAME ONLY": 3, "NOT VERIFIED": 4}
            vcache = load_verified()

            def _apply(d, tier, expl, evid, searches, sources, cached):
                d["confidence"] = tier
                d["resolution"] = {"tier": tier, "explanation": expl,
                    "searches": searches, "sources": sources, "evidence": evid,
                    "from_cache": cached}
                d["source_urls"] = sorted(set(d.get("source_urls", []) + sources))

            def _resolve_fresh(d):
                rr = resolve_relationship(
                    d["person"], d["district_or_town"], d["cannabis_person"],
                    d["cannabis_entity"], d.get("cannabis_residence", ""), offline=False)
                tier = rr.tier
                evid = [(e.kind, e.text, e.source_url) for e in rr.evidence]
                expl = rr.explanation
                # Exact/near-exact name match to a cannabis credential is itself
                # primary-source-grade (the license names this exact person).
                if tier == "SURNAME ONLY" and d.get("same_first") and \
                        d["name_similarity"] >= 86 and not d.get("is_common_surname"):
                    tier = "PROBABLE"
                    expl = (f"A cannabis {d['cannabis_role']} named "
                            f"'{d['cannabis_person']}' (of {d['cannabis_entity']}, "
                            f"{d.get('dcp_or_filing') or 'credential'} "
                            f"{d.get('license_number') or ''}) NAME-MATCHES this "
                            f"official; no independent web confirmation found — VERIFY "
                            f"it is the official and not a namesake.")
                    evid.append(("credential_name_match", expl, ""))
                return tier, expl, evid, rr.searches, rr.sources

            # Rank by (same town, name similarity). CACHED verdicts are reused for
            # FREE; only NEW leads consume the web budget, so verified coverage grows
            # across runs. Once confirmed, a credential never needs re-resolving.
            ranked = sorted(legislator_cannabis_leads,
                            key=lambda d: (not d.get("town_match"), -d["name_similarity"]))
            WEB_BUDGET = 40
            for d in ranked:
                k = vkey(d["person"], d["cannabis_person"], d["cannabis_entity"])
                hit = vcache.get(k)
                if hit and not self.refresh:
                    _apply(d, hit["tier"], hit.get("explanation", ""),
                           hit.get("evidence", []), hit.get("searches", []),
                           hit.get("sources", []), cached=True)
                elif WEB_BUDGET > 0:
                    WEB_BUDGET -= 1
                    tier, expl, evid, searches, sources = _resolve_fresh(d)
                    _apply(d, tier, expl, evid, searches, sources, cached=False)
                    vcache[k] = {"tier": tier, "explanation": expl, "evidence": evid,
                                 "searches": searches, "sources": sources,
                                 "as_of": _date.today().isoformat()}
                else:
                    d["confidence"] = "NOT VERIFIED"
                    d["resolution"] = {"tier": "NOT VERIFIED", "searches": [],
                        "sources": [], "evidence": [], "from_cache": False,
                        "explanation": (f"Surname match only; not web-verified this run "
                            f"(web budget reached). Re-run to resolve — prior verdicts "
                            f"are cached and reused for free.")}
            save_verified(vcache)

            # ---- SPOUSE SECOND-HOP (different-surname spouse) ----------------
            # Find each cannabis-era legislator's spouse from public sources, then
            # cross-reference the spouse NAME against the cannabis credential set.
            # The cross-ref filter makes this safe: a noisy/garbage extracted name
            # almost never matches a real cannabis credential holder, so it does not
            # create false findings — but a true spouse-in-cannabis (different last
            # name) IS caught. Budget-limited + cached (coverage grows across runs).
            try:
                import json
                from datetime import date as _date
                from .config import cache_dir
                from .resolve.relationship import find_spouse_names
                sp_path = cache_dir() / "spouses.json"
                sp_cache = (json.loads(sp_path.read_text(encoding="utf-8"))
                            if sp_path.exists() else {})
                cannabis_by_name = {}
                for p in data["cannabis_persons"]:
                    cannabis_by_name.setdefault(canonical(p.full_name), p)
                already = {l["person"] for l in legislator_cannabis_leads}
                SPOUSE_BUDGET = 50
                # current legislators first (most relevant), then recent formers
                for leg in sorted(screenable, key=lambda l: l.is_former):
                    kcan = canonical(leg.full_name)
                    if kcan in sp_cache and not self.refresh:
                        spouses = sp_cache[kcan]
                    elif SPOUSE_BUDGET > 0:
                        SPOUSE_BUDGET -= 1
                        spouses = find_spouse_names(leg.full_name, offline=False)
                        sp_cache[kcan] = spouses
                    else:
                        continue
                    for sp in spouses:
                        cp = cannabis_by_name.get(canonical(sp))
                        if not cp or surname_key(cp.full_name) == surname_key(leg.full_name):
                            continue  # same-surname already handled; need DIFFERENT
                        role = ("State Senator" if leg.chamber == "Senate"
                                else "State Representative" if leg.chamber == "House"
                                else "Legislator")
                        expl = (f"Public sources name {leg.full_name}'s spouse as "
                                f"'{sp}'. A cannabis {cp.role} of that name "
                                f"('{cp.full_name}', {cp.license_type or 'credential'} "
                                f"{cp.license_number or ''} at {cp.entity_name}) is on "
                                f"record — a DIFFERENT-SURNAME SPOUSE who holds a "
                                f"cannabis credential. VERIFY it is the same person.")
                        legislator_cannabis_leads.append(dict(
                            person=leg.full_name,
                            role=role + (" (former)" if leg.is_former else ""),
                            district_or_town=leg.hometown or leg.district,
                            party=leg.party, years_served=leg.years_served,
                            is_former=leg.is_former, cannabis_person=cp.full_name,
                            cannabis_entity=cp.entity_name, cannabis_role=cp.role,
                            dcp_or_filing=cp.license_type or cp.credential_type,
                            license_number=cp.license_number,
                            cannabis_residence=cp.residence_city,
                            record_date=cp.registration_date,
                            retrieved_date=_date.today().isoformat(),
                            town_match=False, same_first=False,
                            name_similarity=0, is_common_surname=False,
                            confidence="PROBABLE", is_spouse_link=True,
                            source_urls=[cp.provenance.source_url],
                            resolution={"tier": "PROBABLE", "explanation": expl,
                                "searches": [f"web: {leg.full_name} spouse"],
                                "sources": [cp.provenance.source_url],
                                "evidence": [("spouse_credential", expl,
                                              cp.provenance.source_url)]}))
                sp_path.write_text(json.dumps(sp_cache, separators=(",", ":")),
                                   encoding="utf-8")
                checked = sum(1 for v in sp_cache.values() if v)
                self.coverage["Spouse cross-reference (different-surname)"] = {
                    "status": "live", "count": checked,
                    "note": (f"{checked} legislators' spouses identified + cross-checked "
                             f"vs cannabis credential holders (coverage grows per run; "
                             f"SFI spouse-employer data not bulk-available)")}
            except Exception:  # noqa: BLE001
                pass

            # ---- CANNABIS VOTING + TIMELINE (per connected legislator) -------
            try:
                import json
                from datetime import date as _date
                from .config import cache_dir
                from .resolve.voting import cannabis_voting_record
                from .resolve.cga_votes import CgaRollCalls, recusal_search
                vt_path = cache_dir() / "voting.json"
                vt_cache = (json.loads(vt_path.read_text(encoding="utf-8"))
                            if vt_path.exists() else {})
                cga = CgaRollCalls(offline=False, refresh=self.refresh)
                done = set()
                for d in legislator_cannabis_leads:
                    if d.get("confidence") not in ("CONFIRMED", "PROBABLE", "POSSIBLE"):
                        continue
                    kk = canonical(d["person"])
                    if kk in done:
                        d["voting"] = vt_cache.get(kk)
                        continue
                    done.add(kk)
                    if kk in vt_cache and not self.refresh and \
                            "rollcall" in (vt_cache.get(kk) or {}):
                        d["voting"] = vt_cache[kk]
                    else:
                        rec = cannabis_voting_record(
                            d["person"], d.get("years_served", ""),
                            d.get("record_date", ""), offline=False)
                        # ACTUAL per-bill roll-call votes (cga.ct.gov) + recusal check.
                        rec["rollcall"] = cga.legislator_vote(d["person"])
                        rec["recusal"] = recusal_search(d["person"], offline=False)
                        vt_cache[kk] = rec
                        d["voting"] = rec
                vt_path.write_text(json.dumps(vt_cache, separators=(",", ":")),
                                   encoding="utf-8")
            except Exception:  # noqa: BLE001
                pass

            legislator_cannabis_leads.sort(
                key=lambda d: (_TIER_RANK.get(d["confidence"], 9),
                               not d.get("town_match"), -d["name_similarity"]))
            # COMPACT, verified findings cache for quick reference (the resolved
            # connections only — CONFIRMED/PROBABLE/POSSIBLE — with their evidence).
            try:
                import json
                from datetime import date as _d
                from .config import cache_dir
                compact = [{
                    "official": d["person"], "role": d["role"], "town": d["district_or_town"],
                    "party": d["party"], "tier": d["confidence"],
                    "cannabis_person": d["cannabis_person"],
                    "cannabis_residence": d.get("cannabis_residence"),
                    "cannabis_business": d["cannabis_entity"],
                    "cannabis_role": d["cannabis_role"],
                    "license": d.get("license_number"), "record_date": d.get("record_date"),
                    "evidence": [e[1] for e in d.get("resolution", {}).get("evidence", [])],
                    "sources": d.get("resolution", {}).get("sources", []),
                    "as_of": _d.today().isoformat(),
                } for d in legislator_cannabis_leads
                    if d["confidence"] in ("CONFIRMED", "PROBABLE", "POSSIBLE")]
                (cache_dir() / "findings_cache.json").write_text(
                    json.dumps(compact, indent=2), encoding="utf-8")
            except Exception:  # noqa: BLE001
                pass

        # ---- CAMPAIGN FINANCE (SEEC eCRIS) — cannabis money into legislators -----
        # Runs in both modes (offline uses the bundled fixture). Pulls contributions
        # from cannabis operators/principals and ties legislative-recipient ones to a
        # specific legislator.
        campaign_finance: dict = {}
        try:
            campaign_finance = self._campaign_finance(
                screenable, data["cannabis_persons"], legislator_cannabis_leads,
                data["entities"])
            st = campaign_finance.get("status", ("", 0, ""))
            self.coverage["Campaign finance (SEEC eCRIS)"] = {
                "status": ("live" if not self.offline else "fixture"),
                "count": campaign_finance.get("legislative_count", 0),
                "note": (f"{campaign_finance.get('legislative_count', 0)} cannabis-linked "
                         f"contributions to state legislative committees "
                         f"(${campaign_finance.get('legislative_total', 0):,.0f}); "
                         f"{campaign_finance.get('all_count', 0)} cannabis-employer "
                         f"contributions seen overall. " + (st[2] if st else ""))}
        except Exception:  # noqa: BLE001
            campaign_finance = {}

        # ---- LOBBYIST ANALYSIS (CT Office of State Ethics) ----------------------
        lobbying: dict = {}
        try:
            lobbying = self._lobbyist_analysis(
                screenable, data["cannabis_persons"], data["entities"])
            lst = lobbying.get("status", ("", 0, ""))
            self.coverage["Cannabis lobbyists (CT Office of State Ethics)"] = {
                "status": ("live" if not self.offline else "fixture"),
                "count": lobbying.get("cannabis_lobbyist_count", 0),
                "note": (f"{lobbying.get('cannabis_lobbyist_count', 0)} cannabis-industry "
                         f"communicators across {lobbying.get('org_count', 0)} "
                         f"organization(s); {len(lobbying.get('legislator_matches', []))} "
                         f"surname-match(es) to legislators. " + (lst[2] if lst else "")
                         + " Contract-firm client registrations are OSE-portal-only "
                         "(not in this bulk dataset).")}
        except Exception:  # noqa: BLE001
            lobbying = {}

        findings: list[Finding] = []
        review_rows: list[dict] = []
        ref_by_id = {(r.ref_type, r.ref_id): r for r in refs}
        for m in matches:
            leg = leg_by_id[m.person_id]
            amount = amounts.get(m.ref_id)
            confirmed_sfi = m.ref_type == "sfi" and m.ref_id in sfi_confirm
            f = classify_match(leg, m, amount=amount, sfi_confirmed=confirmed_sfi,
                               cfg=self.cfg)
            ref = ref_by_id.get((m.ref_type, m.ref_id))
            if ref:
                url = ref.extra.get("source_url", "")
                if url:
                    f.source_urls = [url]
            findings.append(f)
            # Review queue: every non-publishable match + every family lead.
            if (not f.publishable) or m.is_family_lead or \
               m.confidence in ("PROBABLE", "POSSIBLE/REVIEW"):
                ref = ref_by_id.get((m.ref_type, m.ref_id))
                review_rows.append(dict(
                    person=leg.full_name, district=leg.district,
                    category=m.ref_type, confidence=m.confidence,
                    status=f.status, ref_label=m.ref_label,
                    match_explanation=m.explanation,
                    is_family_lead=m.is_family_lead,
                    source_url=ref.extra.get("source_url", "") if ref else "",
                    legal_basis=f.legal_basis,
                ))

        # Documented recusals (strongest signal). Only the offline fixture corpus
        # carries these; a LIVE bulk run has no recusal feed (meeting minutes are
        # portal-only), so we do NOT inject fixture data into a live run.
        recusal_records = []
        if self.offline:
            try:
                from .collectors.base import load_fixture
                recusal_records = load_fixture("recusals")
            except FileNotFoundError:
                recusal_records = []
        recusals = parse_recusals(recusal_records)

        # Persist
        db_path = db_path or self.cfg["output"]["db_file"]
        store = Store(db_path)
        store.add_legislators(legs)
        store.add_cannabis_entities(data["entities"])
        store.add_cannabis_persons(data["cannabis_persons"])
        store.add_contributions(data["contributions"])
        store.add_lobbyists(data["lobbyists"])
        store.add_sfi(data["sfi"])
        store.add_matches(matches)
        store.add_findings(findings)
        now = datetime.now(timezone.utc).isoformat()
        for name, rows in (("legislators", legs), ("entities", data["entities"]),
                           ("cannabis_persons", data["cannabis_persons"]),
                           ("contributions", data["contributions"]),
                           ("lobbyists", data["lobbyists"]), ("sfi", data["sfi"])):
            store.log_source(name, "(fixture/cache)" if self.offline else "(live)",
                             now, len(rows))
        store.close()

        # Counts that EXACTLY match the report's actual findings (Sections 1-3).
        _flead = legislator_cannabis_leads

        def _n(tier):
            return sum(1 for d in _flead if d.get("confidence") == tier)
        sen = sum(1 for d in _flead if "Senator" in d.get("role", "")
                  and d.get("confidence") in ("CONFIRMED", "PROBABLE", "POSSIBLE"))
        rep = sum(1 for d in _flead if "Representative" in d.get("role", "")
                  and d.get("confidence") in ("CONFIRMED", "PROBABLE", "POSSIBLE"))
        counts = dict(
            legislators=len(legs),
            current=sum(1 for l in legs if not l.is_former),
            former=sum(1 for l in legs if l.is_former),
            cross_referenced=len(screenable),  # cannabis-era subset actually matched
            cannabis_entities=len(data["entities"]),
            cannabis_persons=len(data["cannabis_persons"]),
            contributions=len(data["contributions"]),
            lobbyists=len(data["lobbyists"]),
            sfi=len(data["sfi"]),
            matches=len(matches),
            findings=len(findings),
            published=sum(1 for f in findings if f.publishable),
            review_queue=len(review_rows),
            recusals=len(recusals),
            legislator_cannabis_leads=len(_flead),
            # ---- finding counts that drive the report summary (no contradictions) ----
            confirmed_findings=_n("CONFIRMED"),
            probable_findings=_n("PROBABLE"),
            possible_findings=_n("POSSIBLE"),
            senator_findings=sen,
            representative_findings=rep,
            vote_review_candidates=sen + rep,  # legislators needing a voting review
            cannabis_contributions=campaign_finance.get("legislative_count", 0),
            cannabis_contribution_total=campaign_finance.get("legislative_total", 0.0),
            cannabis_lobbyists=lobbying.get("cannabis_lobbyist_count", 0),
            cannabis_lobbyist_leg_matches=len(lobbying.get("legislator_matches", [])),
        )
        return PipelineResult(
            legislators=legs, findings=findings, recusals=recusals,
            review_rows=review_rows, counts=counts, db_path=db_path,
            coverage=getattr(self, "coverage", {}), mode=("OFFLINE" if self.offline
                                                          else "LIVE"),
            network=getattr(self, "network", None),
            cannabis_persons=data["cannabis_persons"], entities=data["entities"],
            legislator_cannabis_leads=legislator_cannabis_leads,
            campaign_finance=campaign_finance,
            lobbying=lobbying,
        )
