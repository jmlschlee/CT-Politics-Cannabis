"""Reader-facing relationship-tier relabel (V2 #1).

The internal logic strings stay CONFIRMED / PROBABLE / POSSIBLE / SURNAME ONLY
(so the verified-resolution cache, the matcher, and the rest of the suite are
unaffected); the report renders them as VERIFIED / HIGH PROBABILITY / POSSIBLE /
UNVERIFIED NAME MATCH via report.build.display_tier.
"""
from src.report import DISPLAY_TIER, display_tier


def test_each_internal_tier_maps_to_its_display_label():
    assert display_tier("CONFIRMED") == "VERIFIED"
    assert display_tier("PROBABLE") == "HIGH PROBABILITY"
    assert display_tier("POSSIBLE") == "POSSIBLE"
    assert display_tier("SURNAME ONLY") == "UNVERIFIED NAME MATCH"


def test_review_and_not_verified_aliases_map_too():
    # the pipeline/matcher also emit these variants
    assert display_tier("POSSIBLE/REVIEW") == "POSSIBLE"
    assert display_tier("NOT VERIFIED") == "UNVERIFIED NAME MATCH"


def test_mapping_is_case_insensitive_and_passthrough_safe():
    assert display_tier("confirmed") == "VERIFIED"
    # an unknown tier is returned unchanged, never dropped to empty
    assert display_tier("CONTEXT") == "CONTEXT"
    assert display_tier("") == ""
    assert display_tier(None) == ""


def test_no_internal_label_leaks_into_the_display_set():
    # the four reader-facing labels are exactly these and never the old words
    display_values = set(DISPLAY_TIER.values())
    assert display_values == {"VERIFIED", "HIGH PROBABILITY", "POSSIBLE",
                              "UNVERIFIED NAME MATCH"}
    assert "CONFIRMED" not in display_values
    assert "SURNAME ONLY" not in display_values
