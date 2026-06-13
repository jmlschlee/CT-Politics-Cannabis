"""Municipal-module golden cases (§5) — the Simsbury/Curaleaf canonical pattern.
All four output classes must be produced, and the primary-source gate + the
limited-formal-power check must hold."""
import pytest

from src.analyze.municipal import MUNICIPAL_POLICY, parse_minutes
from src.municipal import MunicipalPipeline


@pytest.fixture(scope="module")
def result():
    return MunicipalPipeline(offline=True).run()


def _conns(result, **pred):
    out = result.connections
    for k, v in pred.items():
        out = [c for c in out if getattr(c, k) == v]
    return out


def test_all_four_classes_present(result):
    classes = {c.classification for c in result.connections}
    assert {"CONFIRMED", "UNCONFIRMED", "UNSUPPORTED", "CONTEXT"} <= classes


# 1) siting_official_spouse_attorney -> CONFIRMED appearance concern, not substantial
def test_siting_official_spouse_attorney_confirmed_appearance(result):
    fam = [c for c in result.connections
           if c.connection_type == "official_family_rep"
           and c.subject_kind == "spouse/family"
           and c.classification == "CONFIRMED"]
    assert len(fam) == 1, "expected one CONFIRMED spouse/family appearance concern"
    c = fam[0]
    assert c.subject_name == "Andrew Glassman"
    assert c.appearance_concern is True
    assert c.substantial_conflict is False        # limited formal power + no direct gain
    assert c.confidence == "CONFIRMED"
    # both citations: the family primary source AND the firm's cannabis-practice page
    assert len(c.citations) >= 2
    assert c.review_gated is True                 # private individual -> human review too


# 2) spouse_firm_represents_host_operator -> UNCONFIRMED, not asserted
def test_spouse_firm_host_operator_is_unconfirmed(result):
    firm = [c for c in result.connections
            if c.subject_kind == "firm" and "Curaleaf" in c.subject_name]
    assert firm, "expected an explicit firm -> host-operator connection"
    c = firm[0]
    assert c.classification == "UNCONFIRMED"
    assert c.publishable is False
    # records the firm's ACTUAL documented clients (a different operator)
    assert "Advanced Grow Labs" in c.explanation
    assert "does not support" in c.explanation.lower() or "no source" in c.explanation.lower()


# 3) local_vendor_handles_operator_waste -> REJECTED / negative finding
def test_vendor_waste_is_unsupported_negative(result):
    veh = _conns(result, connection_type="vendor_contractor")
    assert veh and veh[0].classification == "UNSUPPORTED"
    c = veh[0]
    assert c.confidence == "REJECTED"
    assert "no public support" in c.explanation.lower()
    # the national packaging program must NOT be treated as a local link
    assert "national" in c.explanation.lower()
    # a negative is still a publishable result (so the dossier can't read cherry-picked)
    assert c.publishable is True


# 4) legislator_over_host_town -> CONTEXT only
def test_legislator_overlay_is_context(result):
    ov = _conns(result, connection_type="legislative_overlay")
    assert ov and ov[0].classification == "CONTEXT"
    c = ov[0]
    assert c.substantial_conflict is False
    assert "context" in c.explanation.lower()
    assert "Witkos" in c.subject_name


# 5) surname_coincidence_vs_real_family (paired)
def test_real_family_promotes_surname_only_stays_review(result):
    # (a) primary-sourced Glassman marriage -> CONFIRMED (tested above)
    assert any(c.classification == "CONFIRMED" and c.subject_name == "Andrew Glassman"
               for c in result.connections)
    # (b) surname-only Sanchez -> stays UNCONFIRMED / review, never promoted
    san = [c for c in result.connections if c.subject_name == "Elena Sanchez"]
    assert san and san[0].classification == "UNCONFIRMED"
    assert san[0].publishable is False
    assert san[0].is_private_individual is True
    assert "no primary source" in san[0].explanation.lower()


def test_no_substantial_conflict_asserted_anywhere(result):
    # The whole Simsbury case is appearance-level; nothing should be 'substantial'.
    assert result.counts["substantial_conflicts"] == 0


def test_everything_private_is_review_gated(result):
    for c in result.connections:
        if c.is_private_individual and c.classification != "UNSUPPORTED":
            assert c.review_gated is True


def test_minutes_parser_reads_vote_and_no_false_recusal():
    recs = parse_minutes([{
        "town": "X", "body": "P&Z", "date": "2014-01-21",
        "text": "Motion to approve carried 4-2. No member declared a conflict.",
        "vote": "4-2",
    }])
    assert recs[0].ayes == 4 and recs[0].nays == 2
    assert recs[0].approved is True
    assert recs[0].recusals == []     # negated statement is not a recusal


def test_policy_statement_exists():
    assert "appearance is not accusation" in MUNICIPAL_POLICY
    assert "primary source" in MUNICIPAL_POLICY
