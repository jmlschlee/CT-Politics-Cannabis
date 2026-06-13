"""CT Office of State Ethics cannabis-lobbyist analysis (V2 #3)."""
from src.analyze.cannabis_terms import is_cannabis_text
from src.collectors.ose_lobbyists import OseLobbyistCollector, _is_cannabis_org
from src.pipeline import Pipeline


def test_word_boundary_stops_healthcare_false_positive():
    # the substring bug: "thc" inside "healthcare" must NOT flag as cannabis
    assert not is_cannabis_text("Hartford HealthCare")
    assert not is_cannabis_text("Molina Healthcare Inc.")
    assert is_cannabis_text("CT Cannabis Chamber of Commerce")
    assert is_cannabis_text("Budr Cannabis")
    assert is_cannabis_text("cultivation LLC")  # stem still matches


def test_operator_markers_catch_branded_orgs_without_the_word():
    # "Curaleaf" has no generic cannabis term but is a known operator
    assert _is_cannabis_org("Curaleaf", [])
    assert not _is_cannabis_org("Hartford HealthCare", [])
    # registry-supplied extra markers also match
    assert _is_cannabis_org("Greenwich Wellness Co", ["greenwich wellness"])


def test_offline_collector_loads_cannabis_roster():
    c = OseLobbyistCollector(offline=True)
    out = c.collect([])
    assert len(out) == 5
    orgs = {x.client_name for x in out}
    assert "CT Cannabis Chamber of Commerce" in orgs and "Budr Cannabis" in orgs
    assert all(x.is_cannabis for x in out)
    assert c.last_status[0] == "fixture"


def test_pipeline_offline_flags_legislator_who_is_a_cannabis_lobbyist():
    r = Pipeline(offline=True).run()
    lob = r.lobbying
    assert lob["cannabis_lobbyist_count"] == 5
    assert lob["org_count"] == 3
    # Gregory Hallowell is in the roster AND the fixture lobbyist list -> same person
    sm = [m for m in lob["legislator_matches"] if m["same_person"]]
    assert any(m["legislator"] == "Gregory Hallowell" for m in sm)
    assert r.counts["cannabis_lobbyists"] == 5
