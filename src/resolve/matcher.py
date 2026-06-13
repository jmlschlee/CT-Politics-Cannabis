"""Entity resolution — the core of the system.

Given a legislator and a reference record (a DCP credential, a donation, a
business principal, a lobbyist, an SFI line), decide whether they are the same
person and at what confidence, with a human-auditable explanation.

Design rules baked in:
  * Block on surname (incl. variant surnames) before scoring — tractable.
  * Score with rapidfuzz over the legislator's full set of name variants.
  * CONFIRMED requires a strong name match AND >=1 independent disambiguator.
  * Common-surname matches never auto-promote above POSSIBLE/REVIEW.
  * never_merge_pairs (e.g. Candelaria vs Candelora) can NEVER auto-merge.
  * Family/spouse leads are ALWAYS review-gated regardless of score.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from rapidfuzz import fuzz

from ..config import config
from ..models import Confidence, Legislator, Match, RefType
from ..normalize import canonical, name_variants, parse_name, surname_key


@dataclass
class RefRecord:
    """A normalized reference to be matched against legislators."""
    ref_type: RefType
    ref_id: str
    label: str                 # human label for the report ("Key Employee @ Green Leaf LLC")
    name: str                  # the person name as it appears in the source
    hometown: str = ""
    employer: str = ""
    occupation: str = ""
    # UNCERTAIN relative-identity match (e.g. a lobbyist who shares a surname) —
    # forces the result to POSSIBLE/REVIEW no matter how strong the name match.
    is_family_candidate: bool = False
    # The finding CONCERNS a family member, but the identity match to the
    # legislator is itself certain (e.g. an SFI the member personally filed).
    concerns_family: bool = False
    # The source is an authoritative official record keyed to this member (an SFI
    # filing) — the filing itself is the disambiguator, so a strong name match may
    # reach CONFIRMED without a separate corroborator.
    authoritative_identity: bool = False
    extra: dict = field(default_factory=dict)


def _best_name_score(legislator: Legislator, ref_name: str) -> float:
    """Max token-sort similarity of any legislator variant vs the ref name."""
    ref_c = canonical(ref_name)
    variants = legislator.name_variants or name_variants(legislator.full_name)
    if not variants:
        variants = [canonical(legislator.full_name)]
    return max(fuzz.token_sort_ratio(v, ref_c) for v in variants)


def _disambiguators(legislator: Legislator, ref: RefRecord) -> list[str]:
    """Independent corroborating signals shared by legislator and ref."""
    hits: list[str] = []
    lh = canonical(legislator.hometown)
    if lh and ref.hometown and lh == canonical(ref.hometown):
        hits.append(f"hometown {legislator.hometown}")
    locc = canonical(legislator.occupation)
    for field_val, lbl in ((ref.employer, "employer"), (ref.occupation, "occupation")):
        fc = canonical(field_val)
        if fc and locc and (fc in locc or locc in fc):
            hits.append(f"{lbl} corroborates occupation '{legislator.occupation}'")
    # shared middle name/initial is a real disambiguator
    lm = canonical(parse_name(legislator.full_name).middle)
    rm = canonical(parse_name(ref.name).middle)
    if lm and rm and (lm == rm or lm[0] == rm[0]):
        hits.append("middle name/initial agrees")
    return hits


class Matcher:
    def __init__(self, cfg: dict | None = None):
        m = (cfg or config())["matching"]
        self.t = m["thresholds"]
        self.tiers = m["tiers"]
        self.high_collision = {s.lower() for s in m.get("high_collision_surnames", [])}
        self.never_merge = [
            {canonical(a), canonical(b)} for a, b in m.get("never_merge_pairs", [])
        ]

    # -- blocking ---------------------------------------------------------
    def surname_keys(self, legislator: Legislator) -> set[str]:
        keys = {surname_key(legislator.full_name)}
        for v in (legislator.name_variants or name_variants(legislator.full_name)):
            keys.add(surname_key(v))
        return {k for k in keys if k}

    def blocks(self, legislator: Legislator, ref: RefRecord) -> bool:
        return surname_key(ref.name) in self.surname_keys(legislator)

    # -- never-merge guard ------------------------------------------------
    def _forbidden_merge(self, leg_sur: str, ref_sur: str) -> bool:
        if leg_sur == ref_sur:
            return False
        pair = {leg_sur, ref_sur}
        return any(pair == nm for nm in self.never_merge)

    # -- main -------------------------------------------------------------
    def match(self, legislator: Legislator, ref: RefRecord) -> Optional[Match]:
        leg_sur = surname_key(legislator.full_name)
        ref_sur = surname_key(ref.name)

        # Hard guard: explicitly-protected near-collision pairs never merge.
        if self._forbidden_merge(leg_sur, ref_sur):
            return Match(
                person_id=legislator.person_id, ref_type=ref.ref_type,
                ref_id=ref.ref_id, ref_label=ref.label, confidence="REJECTED",
                explanation=(f"surnames '{leg_sur}' vs '{ref_sur}' are a protected "
                             f"near-collision pair — never auto-merged"),
                score=0.0, is_family_lead=ref.is_family_candidate,
            )

        if not self.blocks(legislator, ref):
            return None  # different surname block; not a candidate

        score = _best_name_score(legislator, ref.name)
        disambig = _disambiguators(legislator, ref)
        if score < self.t["name_weak"]:
            # A RELATIVE shares the surname but not the given name, so a low
            # full-name score is expected. Surface it ONLY when a corroborator
            # (e.g. shared hometown) supports a surname/town lead — never on a
            # bare surname coincidence. Non-family low scores are not candidates.
            if not (ref.is_family_candidate and disambig):
                return None
        is_collision = leg_sur in self.high_collision
        confidence, why = self._tier(score, disambig, is_collision,
                                      ref.is_family_candidate, leg_sur,
                                      ref.authoritative_identity)
        # The finding may concern a family member even when the identity is certain.
        finding_is_family = ref.is_family_candidate or ref.concerns_family

        expl_bits = [f"matched on surname '{leg_sur}'", f"name similarity {score:.0f}/100"]
        if disambig:
            expl_bits.append("disambiguators: " + "; ".join(disambig))
        else:
            expl_bits.append("no independent disambiguator")
        if why:
            expl_bits.append(why)

        return Match(
            person_id=legislator.person_id, ref_type=ref.ref_type, ref_id=ref.ref_id,
            ref_label=ref.label, confidence=confidence,
            explanation=" — ".join(expl_bits), score=float(score),
            is_family_lead=finding_is_family,
        )

    def _tier(self, score: float, disambig: list[str], is_collision: bool,
              is_family: bool, surname: str,
              authoritative: bool = False) -> tuple[Confidence, str]:
        # Uncertain family/relative identity is ALWAYS review-gated.
        if is_family:
            return "POSSIBLE/REVIEW", ("family/spouse lead — review-gated; requires an "
                                       "SFI filing or on-the-record source to confirm")
        strong = score >= self.tiers["confirmed_min_name"]
        # An authoritative official filing keyed to this member is self-disambiguating.
        if authoritative and strong and not is_collision:
            return "CONFIRMED", ("authoritative official filing keyed to this member "
                                 "(the filing is itself the disambiguator)")
        if is_collision:
            # Common surname: cannot exceed REVIEW without a disambiguator.
            if strong and disambig:
                return "PROBABLE", (f"common surname '{surname}' with a disambiguator "
                                    f"-> capped at PROBABLE pending human sign-off")
            return "POSSIBLE/REVIEW", (f"common surname '{surname}' — name-only match "
                                       f"held at REVIEW (common-surname guard)")
        if strong and disambig:
            return "CONFIRMED", "strong name match + independent disambiguator"
        if strong and not disambig:
            return "PROBABLE", "strong name match, no independent corroboration"
        if score >= self.tiers["review_min_name"]:
            return "POSSIBLE/REVIEW", "name-only match"
        return "REJECTED", "below review threshold"

    def match_all(self, legislators: list[Legislator],
                  refs: list[RefRecord]) -> list[Match]:
        out: list[Match] = []
        for leg in legislators:
            for ref in refs:
                m = self.match(leg, ref)
                if m and m.confidence != "REJECTED":
                    out.append(m)
        return out
