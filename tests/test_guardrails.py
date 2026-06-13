"""Tests for the non-negotiable guardrails (§6): provenance, privacy, fail-loud."""
import json

import pytest
from pydantic import ValidationError

from src.collectors.base import SourceDriftError
from src.collectors.ethics_sfi import EthicsSFICollector
from src.models import Legislator, Provenance


def test_provenance_is_mandatory():
    with pytest.raises(ValidationError):
        Legislator(person_id="x", full_name="Test Person")  # no provenance


def test_provenance_rejects_empty_source():
    with pytest.raises(ValidationError):
        Provenance(source_name="", source_url="")


def test_sfi_refuses_forbidden_private_fields(tmp_path, monkeypatch):
    """The SFI collector must refuse a feed carrying home address / phone / DOB."""
    bad = [{
        "filing_id": "x", "legislator_name": "Test", "filing_year": 2024,
        "spouse_employer": "Some Cannabis LLC",
        "home_address": "123 Main St",   # forbidden
    }]
    import src.collectors.base as base
    monkeypatch.setattr(base, "load_fixture", lambda name: bad)
    c = EthicsSFICollector(offline=True)
    # force the fixture path (no cache)
    monkeypatch.setattr(c, "cache_read", lambda key: None)
    with pytest.raises(ValueError, match="forbidden"):
        c.collect()


def test_source_drift_error_names_source_and_date():
    err = SourceDriftError("legislators_current", "columns changed")
    msg = str(err)
    assert "legislators_current" in msg
    assert "verified_on" in msg


def test_live_request_blocked_in_offline_mode():
    from src.collectors.legislators_current import LegislatorsCurrentCollector
    c = LegislatorsCurrentCollector(offline=True)
    with pytest.raises(RuntimeError, match="offline"):
        c.http_get("https://example.org")
