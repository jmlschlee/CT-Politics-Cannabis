"""Full-pipeline integration test against local fixtures (no network), with a
deterministic snapshot of the findings table."""
from pathlib import Path

from src.config import config
from src.pipeline import Pipeline
from src.report import write_all

EXPECTED_FINDINGS = [
    ["Diane Folger", "dcp", "HIT — see findings", "PROBABLE", False, False],
    ["Gregory Hallowell", "business", "HIT — see findings", "PROBABLE", False, False],
    ["Jane Doe", "donation", "Appearance concern", "PROBABLE", False, False],
    ["Jane Doe", "donation", "Appearance concern", "PROBABLE", False, False],
    ["Jane Doe", "donation", "Appearance concern", "PROBABLE", False, False],
    ["Karen Whitfield", "lobbyist", "Unable to verify", "POSSIBLE/REVIEW", False, True],
    ["Marcus J. Aldenberry", "dcp", "HIT — see findings", "CONFIRMED", True, False],
    ["Paul Hartley", "sfi", "HIT — see findings", "CONFIRMED", True, True],
]


def _snapshot(result):
    return sorted([f.person_name, f.category, f.status, f.confidence,
                   f.publishable, f.is_family_lead] for f in result.findings)


def test_full_pipeline_snapshot():
    result = Pipeline(offline=True).run(db_path=":memory:")
    assert _snapshot(result) == EXPECTED_FINDINGS


def test_outputs_are_written(tmp_path):
    cfg = config()
    # Redirect outputs into a temp dir so the test is hermetic.
    cfg = {**cfg, "output": {**cfg["output"],
                             "tracker_xlsx": str(tmp_path / "tracker.xlsx"),
                             "findings_md": str(tmp_path / "findings.md"),
                             "findings_pdf": str(tmp_path / "findings.pdf"),
                             "review_queue_csv": str(tmp_path / "review_queue.csv")}}
    result = Pipeline(offline=True).run(db_path=str(tmp_path / "c.duckdb"))
    paths = write_all(result, cfg)
    assert Path(paths["tracker"]).exists()
    assert Path(paths["findings_md"]).exists()
    assert Path(paths["review_queue"]).exists()
    md = Path(paths["findings_md"]).read_text(encoding="utf-8")
    # The caveat and the legal standard must be baked into the report.
    assert "No match found" in md
    assert "§1-84" in md and "§21a-421dd" in md
    assert "UNVERIFIED LEADS" in md


def test_idempotent_offline_zero_network(monkeypatch):
    """Offline mode must never attempt a live request."""
    import src.collectors.base as base

    def _boom(*a, **k):
        raise AssertionError("offline run attempted a live HTTP request")

    monkeypatch.setattr(base.Collector, "http_get", _boom)
    monkeypatch.setattr(base.Collector, "fetch_live", _boom)
    result = Pipeline(offline=True).run(db_path=":memory:")
    assert result.counts["legislators"] == 9


def test_review_queue_has_every_family_lead_and_probable():
    result = Pipeline(offline=True).run(db_path=":memory:")
    # 3 donations (PROBABLE) + Hallowell (PROBABLE) + Folger (PROBABLE) +
    # Whitfield lobbyist (family lead) + Hartley SFI (family, kept for audit) = 7
    assert result.counts["review_queue"] == 7
    fams = [r for r in result.review_rows if r["is_family_lead"]]
    assert any(r["person"] == "Karen Whitfield" for r in fams)
