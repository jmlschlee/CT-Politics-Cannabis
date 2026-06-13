"""Municipal connection taxonomy + four-class classifier.

Models the Simsbury/Curaleaf worked example (§4) as the canonical pattern. For
each (town, operator) it produces TownConnection records in exactly four classes:

  CONFIRMED    — well-sourced kernel (marriage + spouse's cannabis practice)
  UNCONFIRMED  — a specific link the record does NOT support (firm -> host operator)
  UNSUPPORTED  — checked and not found; a NEGATIVE finding (vendor -> operator)
  CONTEXT      — relevant but not a financial conflict (legislator over the town)

Epistemic policy (one paragraph): separate the kernel from the connective tissue;
cite or drop; appearance is not accusation; negatives are findings. A shared
surname/town is a lead, never a finding — family/representation links promote
above REVIEW only on a PRIMARY source.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..models import (
    CannabisFacility, FamilyLink, LawFirm, LegislativeOverlay, LocalEntity,
    MunicipalOfficial, TownConnection, VendorHypothesis,
)
from ..normalize import canonical, name_variants
from .cannabis_terms import is_cannabis_text

MUNICIPAL_POLICY = (
    "Epistemic policy: separate the kernel from the connective tissue; cite or "
    "drop; appearance is not accusation; negatives are findings. A shared surname "
    "or town is a lead, never a finding — family and representation links promote "
    "above REVIEW only on a primary source (a campaign bio naming the spouse, a "
    "financial-disclosure spouse field, a firm page naming the client, a deed or "
    "lease). The limited-formal-power check asks who actually cast the deciding "
    "vote: an official who merely welcomed an approval did not control it."
)

# Recusal/vote cues for the minutes parser.
_RECUSAL_RE = re.compile(r"recus|abstain|declar\w*\s+(?:a\s+)?conflict|step(?:ped)? aside",
                         re.IGNORECASE)
_VOTE_RE = re.compile(r"(\d+)\s*[-–to]+\s*(\d+)")


@dataclass
class MinuteResult:
    town: str
    body: str
    date: str
    agenda_item: str
    vote: str
    ayes: int
    nays: int
    approved: bool
    recusals: list[str]
    source_name: str
    source_url: str


def parse_minutes(records: list[dict]) -> list[MinuteResult]:
    """Extract vote breakdown + recusals from meeting-minute records."""
    out: list[MinuteResult] = []
    for r in records:
        text = f"{r.get('agenda_item','')}\n{r.get('text','')}"
        vote = r.get("vote", "")
        ayes = nays = 0
        m = _VOTE_RE.search(vote or text)
        if m:
            ayes, nays = int(m.group(1)), int(m.group(2))
        # An EXPLICIT recusals key (even an empty list) is authoritative — only
        # scan free text when the field is absent.
        if "recusals" in r:
            recusals = list(r["recusals"])
        else:
            recusals = []
            for line in text.splitlines():
                # Skip negated statements ("No member declared a conflict").
                if re.search(r"\bno\s+(?:member|one|commissioner)\b", line, re.I):
                    continue
                if _RECUSAL_RE.search(line):
                    nm = re.search(r"\b([A-Z][A-Za-z.'-]+\s+[A-Z][A-Za-z.'-]+)\b", line)
                    if nm:
                        recusals.append(nm.group(1))
        out.append(MinuteResult(
            town=r.get("town", ""), body=r.get("body", ""), date=r.get("date", ""),
            agenda_item=r.get("agenda_item", ""), vote=vote or (m.group(0) if m else ""),
            ayes=ayes, nays=nays, approved=(ayes > nays) if (ayes or nays) else
            (r.get("outcome", "").lower() == "approved"),
            recusals=recusals, source_name=r.get("source_name", "meeting_minutes"),
            source_url=r.get("source_url", ""),
        ))
    return out


def _same_person(name: str, official: MunicipalOfficial) -> bool:
    """Identity match between a free name and an official, via canonical variants."""
    cn = canonical(name)
    variants = official.name_variants or name_variants(official.full_name)
    return cn in {canonical(v) for v in variants} or cn == canonical(official.full_name)


def _firm_for(employer: str, firms: list[LawFirm]) -> LawFirm | None:
    ce = canonical(employer)
    for f in firms:
        if ce and ce == canonical(f.name):
            return f
    return None


def _decided_the_siting(official: MunicipalOfficial, facility: CannabisFacility) -> bool:
    """Limited-formal-power check: was this official actually on the body that voted?
    A First Selectman who *welcomes* a Zoning Commission approval did NOT decide it."""
    return bool(facility.approval_body) and \
        canonical(official.body) == canonical(facility.approval_body)


@dataclass
class TownDossier:
    town: str
    operator: str
    facility: CannabisFacility
    connections: list[TownConnection] = field(default_factory=list)

    def by_class(self, klass: str) -> list[TownConnection]:
        return [c for c in self.connections if c.classification == klass]


def _cite(*parts: str) -> list[str]:
    return [p for p in parts if p]


def classify_facility(
    facility: CannabisFacility,
    officials: list[MunicipalOfficial],
    family_links: list[FamilyLink],
    firms: list[LawFirm],
    vendors: list[VendorHypothesis],
    overlays: list[LegislativeOverlay],
    minutes: list[MinuteResult],
) -> TownDossier:
    town, op = facility.town, facility.operator_name
    dossier = TownDossier(town=town, operator=op, facility=facility)
    add = dossier.connections.append
    town_officials = [o for o in officials if canonical(o.town) == canonical(town)]
    town_minutes = [m for m in minutes if canonical(m.town) == canonical(town)]

    # -- 1) SITING / ZONING (context; conflict only if decider AND gainer) -----
    recused = sorted({n for m in town_minutes for n in m.recusals})
    vote_note = ""
    if facility.approval_vote:
        vote_note = f" on a {facility.approval_vote} vote"
    elif town_minutes:
        vote_note = f" on a {town_minutes[0].vote} vote"
    add(TownConnection(
        town=town, operator=op, subject_name=facility.approval_body or "(approving body)",
        subject_kind="official", connection_type="siting_zoning",
        classification="CONTEXT", appearance_concern=False, substantial_conflict=False,
        explanation=(f"{op} sited at {facility.address or town}; "
                     f"{facility.approval_outcome or 'approved'} by "
                     f"{facility.approval_body or 'the local body'}{vote_note}." +
                     (f" Recusals on record: {', '.join(recused)}." if recused else
                      " No recusals on record.")),
        citations=_cite(facility.provenance.source_url),
        publishable=True,
    ))

    # -- per-official analysis ------------------------------------------------
    for off in town_officials:
        in_office = (not off.in_office_at) or (facility.facility_id in off.in_office_at)
        if not in_office:
            continue
        decided = _decided_the_siting(off, facility)

        # 3) OFFICIAL'S OWN ROLE — direct stake => substantial conflict
        if off.owns_operator_parcel or "licensee" in off.own_role_note.lower() \
                or "backer" in off.own_role_note.lower():
            add(TownConnection(
                town=town, operator=op, subject_name=off.full_name,
                subject_kind="official", connection_type="official_own_role",
                classification="CONFIRMED", appearance_concern=True,
                substantial_conflict=True,
                explanation=(f"{off.full_name} ({off.role or off.body}) has a direct "
                             f"role: {off.own_role_note or 'landlord to the operator'}."),
                citations=_cite(off.provenance.source_url), publishable=True,
            ))

        # 2) OFFICIAL FAMILY EMPLOYMENT / REPRESENTATION
        for fl in family_links:
            if not _same_person(fl.official_name, off):
                continue
            relative_is_cannabis = is_cannabis_text(fl.relative_role) or \
                is_cannabis_text(fl.relative_employer)
            if not relative_is_cannabis:
                continue
            firm = _firm_for(fl.relative_employer, firms)

            if not fl.is_primary_source:
                # PRIMARY-SOURCE GATE: a relationship asserted without a primary
                # source is a LEAD, never a finding. Stays REVIEW.
                add(TownConnection(
                    town=town, operator=op, subject_name=fl.relative_name,
                    subject_kind="spouse/family", connection_type="official_family_rep",
                    classification="UNCONFIRMED", confidence="POSSIBLE/REVIEW",
                    explanation=(f"Possible {fl.relationship or 'relative'} tie between "
                                 f"{off.full_name} and cannabis-affiliated "
                                 f"{fl.relative_name} — NO primary source "
                                 f"({fl.source_type or 'uncorroborated'}); confirm "
                                 f"against a primary source before any finding."),
                    citations=_cite(fl.provenance.source_url),
                    is_private_individual=True, review_gated=True, publishable=False,
                ))
                continue

            # Primary-sourced: the relationship + the relative's cannabis practice
            # are CONFIRMED. Whether it is a SUBSTANTIAL conflict depends on the
            # limited-formal-power check + a shown direct gain.
            firm_reps_host = bool(firm and any(
                canonical(op) == canonical(c) for c in firm.cannabis_clients))
            substantial = decided and firm_reps_host
            add(TownConnection(
                town=town, operator=op, subject_name=fl.relative_name,
                subject_kind="spouse/family", connection_type="official_family_rep",
                classification="CONFIRMED", confidence="CONFIRMED",
                appearance_concern=True, substantial_conflict=substantial,
                explanation=(
                    f"{off.full_name} ({off.role or off.body}) is {fl.relationship} of "
                    f"{fl.relative_name}, {fl.relative_role}"
                    f"{' at ' + fl.relative_employer if fl.relative_employer else ''} "
                    f"(relationship confirmed by primary source: {fl.source_type}). "
                    + ("This official did NOT sit on the body that approved the siting "
                       "(limited formal power) — appearance concern, not a substantial "
                       "conflict." if not decided else
                       "This official sat on the deciding body — weigh recusal.")
                ),
                citations=_cite(fl.provenance.source_url,
                                firm.provenance.source_url if firm else ""),
                is_private_individual=True, review_gated=True, publishable=True,
            ))

            # 2b) The SPECIFIC firm -> HOST-operator representation. Do NOT assert it
            # unless documented; if the firm's documented clients are OTHER operators,
            # record that and mark the host-operator representation UNVERIFIED.
            if firm and not firm_reps_host:
                others = ", ".join(firm.cannabis_clients) or "(none documented)"
                add(TownConnection(
                    town=town, operator=op, subject_name=f"{firm.name} → {op}",
                    subject_kind="firm", connection_type="official_family_rep",
                    classification="UNCONFIRMED", confidence="POSSIBLE/REVIEW",
                    explanation=(
                        f"No source shows {firm.name} represents the host operator "
                        f"{op} or worked this siting. The firm's documented cannabis "
                        f"clients are: {others}. The 'spouse's firm → host operator' "
                        f"link is an INFERENCE the record does not support."),
                    citations=_cite(firm.provenance.source_url),
                    is_private_individual=True, review_gated=True, publishable=False,
                ))

    # -- 4) VENDOR / CONTRACTOR — documented or it is a NEGATIVE finding -------
    for v in vendors:
        if canonical(v.operator_name) != canonical(op):
            continue
        if canonical(v.town) and canonical(v.town) != canonical(town):
            continue
        if v.evidence_found:
            add(TownConnection(
                town=town, operator=op, subject_name=v.vendor_name,
                subject_kind="local_entity", connection_type="vendor_contractor",
                classification="CONFIRMED", confidence="CONFIRMED",
                appearance_concern=True,
                explanation=f"Documented transaction: {v.note or v.hypothesis}.",
                citations=_cite(v.provenance.source_url),
                is_private_individual=True, review_gated=True, publishable=True,
            ))
        else:
            extra = (" The only 'recycling' tie is a NATIONAL packaging program, "
                     "unrelated to this local business." if v.national_program_only
                     else "")
            add(TownConnection(
                town=town, operator=op, subject_name=v.vendor_name,
                subject_kind="local_entity", connection_type="vendor_contractor",
                classification="UNSUPPORTED", confidence="REJECTED",
                explanation=(f"Checked hypothesis '{v.hypothesis}': NO public support "
                             f"for a {v.vendor_name} → {op} link. {v.note}{extra}"),
                citations=_cite(v.provenance.source_url), publishable=True,
            ))

    # -- 6) LEGISLATIVE OVERLAY — context only --------------------------------
    for ov in overlays:
        if not any(canonical(town) == canonical(t) for t in ov.towns_represented):
            continue
        if canonical(ov.financial_stake) in ("", "none", "n/a"):
            add(TownConnection(
                town=town, operator=op, subject_name=ov.legislator_name,
                subject_kind="legislator", connection_type="legislative_overlay",
                classification="CONTEXT", appearance_concern=False,
                substantial_conflict=False,
                explanation=(f"{ov.legislator_name} ({ov.chamber} {ov.district}) "
                             f"represents {town}"
                             f"{' and sat on ' + ov.committee if ov.committee else ''}"
                             f"; employer {ov.employer or 'n/a'}, no cannabis financial "
                             f"stake surfaced — geographic + committee context, not a "
                             f"conflict."),
                citations=_cite(ov.provenance.source_url), publishable=True,
            ))

    return dossier
