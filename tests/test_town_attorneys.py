"""Town-attorney cannabis chains + municipal host-town expansion (V2 #4)."""
from src.collectors.town_attorneys import TownAttorneyChains, _firm_key
from src.municipal import MunicipalPipeline


def test_firm_key_drops_entity_suffix():
    assert _firm_key("Pullman & Comley LLC") == "pullman & comley"
    assert _firm_key("Updike, Kelly & Spellacy, P.C.") == "updike kelly & spellacy"


def test_match_firm_finds_registry_firm_in_text():
    tac = TownAttorneyChains(offline=True)
    f = tac.match_firm("The town retained Pullman & Comley as corporation counsel.")
    assert f and f["firm"] == "Pullman & Comley LLC"
    assert tac.match_firm("Some unrelated firm Smith & Jones") is None


def test_sourced_findings_include_simsbury_pullman():
    tac = TownAttorneyChains(offline=True)
    sf = tac.sourced_findings()
    assert any(f["town"] == "Simsbury" and "Pullman" in f["firm"] for f in sf)
    # every sourced finding carries a citation and is NOT a fabricated discovery
    assert all(f["sources"] and not f["discovered"] for f in sf)


def test_discover_is_offline_safe():
    # offline must never web-search or fabricate a town-counsel link
    assert TownAttorneyChains(offline=True).discover_town_counsel("Montville") is None


def test_municipal_expansion_builds_roster_and_chains():
    m = MunicipalPipeline(offline=True).run()
    assert m.host_town_roster, "expected a host-town roster"
    sims = [g for g in m.host_town_roster if g["town"] == "Simsbury"]
    assert sims and sims[0]["cannabis_counsel"] is True
    assert sims[0]["counsel"] == "Pullman & Comley LLC"
    assert any(f["town"] == "Simsbury" for f in m.town_attorney_findings)
    assert m.counts["town_attorney_chains"] >= 1
