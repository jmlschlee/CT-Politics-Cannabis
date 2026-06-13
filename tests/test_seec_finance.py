"""SEEC eCRIS campaign-finance collector + pipeline integration (V2 #2)."""
from src.collectors.seec_finance import (
    SeecCampaignFinance, parse_grid, normalize_entity, is_legislative,
)
from src.models import CampaignContribution, Provenance
from src.pipeline import Pipeline


def _prov():
    return Provenance(source_name="t", source_url="https://seec.ct.gov/x")


# A trimmed two-row sample of the real gvSearchResult grid.
_GRID = """
<table id="ctl00_ContentPlaceHolder1_gvSearchResult">
  <tr><th>Receipt ID</th><th>Committee</th><th>Received From</th><th>City</th>
      <th>Office Sought</th><th>District</th><th>Employer</th>
      <th>Transaction Date</th><th>Amount</th></tr>
  <tr><td>C1224991</td><td>Witkos 2020</td><td>Eleanor Brightwood</td><td>Canton</td>
      <td>State Senator</td><td>8</td><td>Curaleaf</td><td>05/11/2020</td>
      <td>50.00</td></tr>
</table>
"""


def test_parse_grid_maps_headers_to_values():
    rows = parse_grid(_GRID)
    assert len(rows) == 1
    r = rows[0]
    assert r["Received From"] == "Eleanor Brightwood"
    assert r["Office Sought"] == "State Senator"
    assert r["Employer"] == "Curaleaf"
    assert r["Amount"] == "50.00"


def test_normalize_entity_strips_corporate_suffix():
    assert normalize_entity("Curaleaf CT, LLC") == "curaleaf"
    assert normalize_entity("Green Vale Micro-Cultivation LLC") == "green vale micro cultivation"
    # collapses two spellings of the same operator to one search term
    assert normalize_entity("Curaleaf") == normalize_entity("Curaleaf Holdings Inc")


def test_is_legislative_only_state_legislative_offices():
    leg = CampaignContribution(receipt_id="1", contributor_name="X",
                               office_sought="State Senator", provenance=_prov())
    gov = CampaignContribution(receipt_id="2", contributor_name="Y",
                               office_sought="Governor", provenance=_prov())
    assert is_legislative(leg) and not is_legislative(gov)


def test_offline_collector_loads_fixture():
    c = SeecCampaignFinance(offline=True)
    out = c.collect(["Curaleaf"], ["Diane Folger"])
    assert len(out) == 3
    assert any(x.contributor_name == "Eleanor Brightwood" and x.employer == "Curaleaf"
               for x in out)
    assert c.last_status[0] == "fixture"


def test_offline_collector_makes_no_network_call(monkeypatch):
    # Offline must never import/use httpx — guard against accidental live calls.
    import src.collectors.seec_finance as mod
    monkeypatch.setattr(mod.SeecContributionSearch, "search",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    out = SeecCampaignFinance(offline=True).collect(["Curaleaf"], [])
    assert len(out) == 3  # served entirely from the fixture


def test_pipeline_offline_surfaces_campaign_finance():
    r = Pipeline(offline=True).run()
    cf = r.campaign_finance
    assert cf["legislative_count"] == 3
    assert cf["legislative_total"] == 400.0
    # Aldenberry + Folger are in the fixture roster -> linked; Witkos is not.
    assert set(cf["linked_legislators"]) == {"Marcus J. Aldenberry", "Diane Folger"}
    assert r.counts["cannabis_contributions"] == 3
    # every legislative recipient row carries a clickable eCRIS source
    assert all(g["sources"] for g in cf["by_recipient"])
