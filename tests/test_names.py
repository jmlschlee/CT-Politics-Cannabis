"""Unit tests for the name-variant generator and parser."""
from src.normalize import name_variants, parse_name, surname_key, canonical


def test_parse_space_form():
    # parse_name preserves display case; canonicalization happens downstream.
    p = parse_name("Marcus J. Aldenberry")
    assert (p.first, p.middle, p.last) == ("Marcus", "J", "Aldenberry")


def test_parse_comma_form_with_suffix():
    p = parse_name("Smith-Jones, Robert J. Jr.")
    assert p.first == "Robert"
    assert p.last == "Smith-Jones"
    assert p.suffix == "jr"


def test_nickname_expansion_both_directions():
    # Robert -> Bob and friends
    vs = name_variants("Robert Smith")
    assert "bob smith" in vs
    assert "robert smith" in vs
    # and Bob -> Robert
    vs2 = name_variants("Bob Smith")
    assert "robert smith" in vs2


def test_quoted_nickname_extracted():
    vs = name_variants('William "Bill" Hayes')
    assert "bill hayes" in vs
    assert "william hayes" in vs


def test_maiden_name_variant():
    vs = name_variants("Jane Doe", maiden="Roberts")
    assert "jane doe" in vs
    assert "jane roberts" in vs


def test_hyphenated_surname_components():
    vs = name_variants("Maria Santos-Cruz")
    # each component usable alone for recall
    assert any(v.endswith("santos") for v in vs)
    assert any(v.endswith("cruz") for v in vs)


def test_accent_stripping():
    assert canonical("José Peña") == "jose pena"
    vs = name_variants("José Peña")
    assert "jose pena" in vs


def test_surname_key_uses_primary_component():
    assert surname_key("Maria Santos-Cruz") == "santos"
    assert surname_key("Vincent Candelora") == "candelora"
    assert surname_key("Juan Candelaria") == "candelaria"
