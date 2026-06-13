"""Acceptance / golden-case tests (the matcher MUST surface these)."""
import pytest

from src.pipeline import Pipeline


@pytest.fixture(scope="module")
def result():
    # in-memory store; offline = fixtures only, zero live requests
    return Pipeline(offline=True).run(db_path=":memory:")


def _findings(result, person=None, category=None):
    out = result.findings
    if person:
        out = [f for f in out if f.person_name == person]
    if category:
        out = [f for f in out if f.category == category]
    return out


def test_dcp_key_employee_surfaced_without_backer_record(result):
    """Must surface a legislator's appearance in the DCP key-employee roster even
    when NO business/backer ownership record exists (the prior manual-pass miss)."""
    f = _findings(result, person="Marcus J. Aldenberry", category="dcp")
    assert f, "key-employee credential was not surfaced"
    assert f[0].status == "HIT — see findings"
    assert f[0].confidence == "CONFIRMED"
    assert "key-employee" in f[0].citations[0] or "key_employee" in f[0].explanation \
        or "Green Vale" in f[0].citations[0]
    # And there is no backer/business record for him anywhere.
    assert not _findings(result, person="Marcus J. Aldenberry", category="business")


def test_small_dispensary_donations_are_appearance_concern(result):
    """Three $250 dispensary contributions to one PAC -> caught + classified as
    an Appearance concern under the §1-85 class exception."""
    dons = _findings(result, person="Jane Doe", category="donation")
    assert len(dons) == 3, f"expected 3 donation findings, got {len(dons)}"
    for d in dons:
        assert d.status == "Appearance concern"
        assert "class exception" in d.legal_basis.lower()


def test_family_lobbyist_is_review_not_finding(result):
    """A legislator sharing surname+hometown with a registered cannabis lobbyist
    lands in the review queue as POSSIBLE/REVIEW — and is NOT a published finding
    (no SFI confirmation exists for her)."""
    lob = _findings(result, person="Karen Whitfield", category="lobbyist")
    assert lob, "lobbyist family lead not surfaced"
    assert lob[0].confidence == "POSSIBLE/REVIEW"
    assert lob[0].is_family_lead is True
    assert lob[0].publishable is False
    # present in the review queue with an explanation + source
    rows = [r for r in result.review_rows
            if r["person"] == "Karen Whitfield" and r["category"] == "lobbyist"]
    assert rows and rows[0]["match_explanation"]
    assert rows[0]["source_url"]
    # never a published finding
    assert all(not f.publishable for f in lob)


def test_sfi_confirmation_promotes_family_tie_to_finding(result):
    """When an SFI filing supplies the spouse-employer confirmation, the family
    tie DOES become a publishable, cited finding."""
    sfi = _findings(result, person="Paul Hartley", category="sfi")
    assert sfi, "SFI spouse-employer tie not surfaced"
    assert sfi[0].status == "HIT — see findings"
    assert sfi[0].publishable is True
    assert sfi[0].is_family_lead is True
    assert "SFI" in " ".join(sfi[0].legal_basis.split()) or "SFI" in sfi[0].explanation


def test_former_legislator_is_in_scope(result):
    """Former members are screened (the §21a-421dd 2-yr cooling-off)."""
    assert any(l.is_former for l in result.legislators)
    folger = _findings(result, person="Diane Folger", category="dcp")
    assert folger, "former-legislator cannabis credential not surfaced"


def test_recusal_parser_only_cannabis(result):
    """The documented-recusal section surfaces the cannabis recusal and ignores a
    generic (non-cannabis) abstention."""
    names = {r.member_name for r in result.recusals}
    assert "Jane Doe" in names          # cannabis licensing recusal
    assert "Michael Brown" not in names  # generic scheduling abstention


def test_no_match_is_not_proof(result):
    """A member with no cannabis tie shows 'No match found', not a finding."""
    # Michael Brown's only contribution is non-cannabis -> no donation finding.
    assert not _findings(result, person="Michael Brown", category="donation")
