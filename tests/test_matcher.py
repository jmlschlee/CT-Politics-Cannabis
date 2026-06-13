"""Unit tests for the entity-resolution confidence scorer and guards."""
from src.models import Legislator, Provenance
from src.normalize import name_variants
from src.resolve import Matcher, RefRecord


def _leg(name, **kw) -> Legislator:
    return Legislator(
        person_id=kw.get("person_id", name.lower().replace(" ", "-")),
        full_name=name, name_variants=name_variants(name),
        hometown=kw.get("hometown", ""), occupation=kw.get("occupation", ""),
        chamber=kw.get("chamber", "House"), district=kw.get("district", "1"),
        provenance=Provenance(source_name="t", source_url="http://t"),
    )


def test_confirmed_requires_disambiguator():
    m = Matcher()
    leg = _leg("Marcus Aldenberry", hometown="Glastonbury")
    # name-only -> PROBABLE, not CONFIRMED
    ref = RefRecord("dcp", "r1", "key emp", "Marcus Aldenberry")
    assert m.match(leg, ref).confidence == "PROBABLE"
    # with a shared hometown -> CONFIRMED
    ref2 = RefRecord("dcp", "r2", "key emp", "Marcus Aldenberry", hometown="Glastonbury")
    assert m.match(leg, ref2).confidence == "CONFIRMED"


def test_middle_initial_is_a_disambiguator():
    m = Matcher()
    leg = _leg("Marcus J. Aldenberry")
    ref = RefRecord("dcp", "r", "key emp", "Marcus J. Aldenberry")
    assert m.match(leg, ref).confidence == "CONFIRMED"


def test_common_surname_guard_caps_at_review():
    m = Matcher()
    leg = _leg("Michael Brown", hometown="Groton")  # 'brown' is high-collision
    ref = RefRecord("dcp", "r", "key emp", "Michael Brown")  # name only
    assert m.match(leg, ref).confidence == "POSSIBLE/REVIEW"
    # even with a disambiguator a common surname is capped at PROBABLE (needs sign-off)
    ref2 = RefRecord("dcp", "r2", "key emp", "Michael Brown", hometown="Groton")
    assert m.match(leg, ref2).confidence == "PROBABLE"


def test_candelaria_candelora_never_merge():
    m = Matcher()
    leg = _leg("Juan Candelaria", district="95")
    ref = RefRecord("business", "r", "principal", "Vincent Candelora")
    res = m.match(leg, ref)
    assert res is not None and res.confidence == "REJECTED"
    # and the reverse direction
    leg2 = _leg("Vincent Candelora", district="86")
    ref2 = RefRecord("business", "r2", "principal", "Juan Candelaria")
    assert m.match(leg2, ref2).confidence == "REJECTED"


def test_different_surname_does_not_block():
    m = Matcher()
    leg = _leg("Jane Doe")
    ref = RefRecord("dcp", "r", "key emp", "Karen Whitfield")
    assert m.match(leg, ref) is None


def test_family_candidate_forced_to_review():
    m = Matcher()
    leg = _leg("Karen Whitfield", hometown="Rocky Hill")
    ref = RefRecord("lobbyist", "r", "cannabis lobbyist", "Thomas Whitfield",
                    hometown="Rocky Hill", is_family_candidate=True)
    res = m.match(leg, ref)
    assert res.confidence == "POSSIBLE/REVIEW"
    assert res.is_family_lead is True


def test_authoritative_sfi_can_confirm():
    m = Matcher()
    leg = _leg("Paul Hartley")
    ref = RefRecord("sfi", "r", "SFI spouse employer", "Paul Hartley",
                    concerns_family=True, authoritative_identity=True)
    res = m.match(leg, ref)
    assert res.confidence == "CONFIRMED"
    assert res.is_family_lead is True   # still flagged as concerning family
