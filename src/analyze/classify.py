"""Classify each cross-reference match against the Connecticut legal standard.

The report states the standard plainly:

  CGS §1-84 / §1-85 — a "substantial conflict" requiring recusal exists only
  where the legislator, spouse, dependent child, or an associated business
  (5%+ ownership or officer/director) derives a DIRECT monetary gain or loss.
  The §1-85 "class exception" permits voting where the interest is no greater
  than to others in the same profession/occupation/group — so broad,
  industry-wide bills plus small donations generally do NOT meet the bar.

  Conn. Gen. Stat. §21a-421dd (RERACA) — a sitting legislator may not apply for
  a cannabis establishment license; a 2-year post-service cooling-off applies to
  former legislators (this is why the historical roster matters).

This module ATTACHES a legal frame and a status. It does not accuse. Anything
touching family, and anything below CONFIRMED, is routed to the review queue by
the report layer — never auto-published as a confirmed conflict.
"""
from __future__ import annotations

from ..config import config
from ..models import Finding, Legislator, Match

LEGAL_PREAMBLE = (
    "LEGAL STANDARD (stated plainly): Under CGS §1-84/§1-85 a 'substantial "
    "conflict' requiring recusal exists only where the legislator, their spouse, "
    "a dependent child, or an associated business (5%+ ownership or "
    "officer/director) derives a DIRECT monetary gain or loss from the matter. "
    "The §1-85 'class exception' permits voting where the legislator's interest "
    "is no greater than that of others in the same profession/occupation/group, "
    "so broad industry-wide bills and small contributions generally do not meet "
    "the bar. Conn. Gen. Stat. §21a-421dd bars a SITTING legislator from applying "
    "for a cannabis establishment license and imposes a 2-year cooling-off period "
    "on FORMER legislators. This report is a screening aid: absence of a match is "
    "'no match found,' not proof of no involvement, and every family/spouse item "
    "and every potential hit is routed to human review with its citations."
)

# Donation total (per recipient committee, per source) above which a confirmed
# cannabis-industry donation rises from a pure class-exception 'appearance' note.
_LARGE_DONATION = 1000.0


def _citation(match: Match, legislator: Legislator) -> str:
    return f"{match.ref_type}:{match.ref_id} ({match.ref_label})"


def classify_match(legislator: Legislator, match: Match,
                   amount: float | None = None,
                   sfi_confirmed: bool = False,
                   cfg: dict | None = None) -> Finding:
    """Produce a Finding for one match. The report layer decides publish-vs-review."""
    cfg = cfg or config()
    legal = cfg["legal"]
    cite = _citation(match, legislator)
    confirmed = match.confidence == "CONFIRMED"
    probable = match.confidence == "PROBABLE"

    base = dict(
        person_id=legislator.person_id, person_name=legislator.full_name,
        category=match.ref_type, confidence=match.confidence,
        citations=[cite], is_family_lead=match.is_family_lead,
    )
    expl = match.explanation

    def finalize(f: Finding) -> Finding:
        """A finding may be PUBLISHED only if it is a HIT/Appearance concern, the
        identity is CONFIRMED, and it is either not family-related or has been
        confirmed by an SFI filing. Everything else is review-queue-only."""
        strong_identity = f.confidence == "CONFIRMED" or sfi_confirmed
        f.publishable = (
            f.status in ("HIT — see findings", "Appearance concern")
            and strong_identity
            and (not f.is_family_lead or sfi_confirmed)
        )
        return f

    # ---- DCP credential / business principal = potential DIRECT stake -----
    if match.ref_type in ("dcp", "business"):
        if match.is_family_lead and not sfi_confirmed:
            return finalize(Finding(**base, status="Unable to verify", priority="LOW",
                           legal_basis=f"{legal['cgs_substantial_conflict']} "
                                       f"(family lead — unconfirmed)",
                           explanation=match.explanation +
                           " | family/relative tie — held for SFI/on-record confirmation"))
        if confirmed or sfi_confirmed:
            basis = legal["cgs_substantial_conflict"]
            if not legislator.is_former:
                basis += f"; {legal['reraca']} (sitting member may not apply for a license)"
            else:
                basis += f"; {legal['reraca']} 2-yr cooling-off (former member)"
            return finalize(Finding(**base, status="HIT — see findings", priority="HIGH",
                           legal_basis=basis, explanation=expl))
        if probable:
            return finalize(Finding(**base, status="HIT — see findings", priority="MEDIUM",
                           legal_basis=legal["cgs_substantial_conflict"] +
                           " (probable — verify identity)", explanation=expl))
        return finalize(Finding(**base, status="Unable to verify", priority="LOW",
                       legal_basis=legal["cgs_substantial_conflict"] + " (review)",
                       explanation=expl))

    # ---- Campaign donations = §1-85 class-exception territory --------------
    if match.ref_type == "donation":
        large = amount is not None and amount >= _LARGE_DONATION
        priority = "MEDIUM" if (confirmed and large) else "LOW"
        note = (" | concentrated/large contribution — weigh against the class "
                "exception" if large else
                " | small/industry-wide contribution — class exception likely applies")
        return finalize(Finding(**base, status="Appearance concern", priority=priority,
                       legal_basis=legal["cgs_class_exception"] + " (class exception)",
                       explanation=match.explanation + note))

    # ---- Lobbyist family tie -------------------------------------------
    if match.ref_type == "lobbyist":
        return finalize(Finding(**base, status="Unable to verify", priority="LOW",
                       legal_basis=legal["cgs_substantial_conflict"] +
                       " (relative-lobbyist lead)",
                       explanation=match.explanation +
                       " | possible relative who lobbies for cannabis clients — "
                       "review-gated, confirm relationship before any finding"))

    # ---- SFI spouse/family employer ------------------------------------
    if match.ref_type == "sfi":
        if sfi_confirmed:
            return finalize(Finding(**base, status="HIT — see findings", priority="HIGH",
                           legal_basis=legal["cgs_substantial_conflict"] +
                           " (spouse/family employed by a cannabis business per SFI)",
                           explanation=match.explanation +
                           " | confirmed by Statement of Financial Interests filing"))
        return finalize(Finding(**base, status="Unable to verify", priority="LOW",
                       legal_basis=legal["cgs_substantial_conflict"] + " (SFI lead)",
                       explanation=expl))

    # default safety net
    return finalize(Finding(**base, status="Unable to verify", priority="LOW",
                   legal_basis=legal["cgs_substantial_conflict"], explanation=expl))
