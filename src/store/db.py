"""DuckDB-backed normalized store with mandatory provenance.

Every externally-sourced row carries (source_name, source_url, retrieved_at).
The insert helpers take typed models and refuse rows lacking provenance.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import duckdb

from ..models import (
    CannabisEntity,
    CannabisPerson,
    Contribution,
    Finding,
    Legislator,
    Lobbyist,
    Match,
    SFIFiling,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS legislators (
    person_id TEXT PRIMARY KEY,
    full_name TEXT, first TEXT, middle TEXT, last TEXT, suffix TEXT,
    chamber TEXT, district TEXT, party TEXT, hometown TEXT,
    first_elected INTEGER, years_served TEXT, occupation TEXT,
    committees TEXT, is_former BOOLEAN,
    source_name TEXT, source_url TEXT, retrieved_at TEXT
);
CREATE TABLE IF NOT EXISTS name_variants (
    person_id TEXT, variant TEXT, variant_type TEXT
);
CREATE TABLE IF NOT EXISTS cannabis_entities (
    entity_id TEXT PRIMARY KEY,
    name TEXT, entity_type TEXT, license_type TEXT, status TEXT,
    source_name TEXT, source_url TEXT, retrieved_at TEXT
);
CREATE TABLE IF NOT EXISTS cannabis_persons (
    cp_id TEXT PRIMARY KEY,
    full_name TEXT, role TEXT, credential_type TEXT, entity_name TEXT,
    source_kind TEXT,
    source_name TEXT, source_url TEXT, retrieved_at TEXT
);
CREATE TABLE IF NOT EXISTS contributions (
    contrib_id TEXT PRIMARY KEY,
    contributor_name TEXT, employer TEXT, occupation TEXT,
    amount DOUBLE, date TEXT, recipient_committee TEXT,
    source_name TEXT, source_url TEXT, retrieved_at TEXT
);
CREATE TABLE IF NOT EXISTS lobbyists (
    lobbyist_id TEXT PRIMARY KEY,
    communicator_name TEXT, client_name TEXT, is_cannabis BOOLEAN,
    registration_year INTEGER, hometown TEXT,
    source_name TEXT, source_url TEXT, retrieved_at TEXT
);
CREATE TABLE IF NOT EXISTS sfi (
    filing_id TEXT PRIMARY KEY,
    legislator_name TEXT, filing_year INTEGER,
    spouse_employer TEXT, associated_business TEXT,
    source_name TEXT, source_url TEXT, retrieved_at TEXT
);
CREATE TABLE IF NOT EXISTS matches (
    person_id TEXT, ref_type TEXT, ref_id TEXT, ref_label TEXT,
    confidence TEXT, explanation TEXT, score DOUBLE, is_family_lead BOOLEAN
);
CREATE TABLE IF NOT EXISTS findings (
    person_id TEXT, person_name TEXT, category TEXT, status TEXT,
    confidence TEXT, priority TEXT, legal_basis TEXT, explanation TEXT,
    citations TEXT, is_family_lead BOOLEAN
);
-- Raw cached payloads, so the store is self-documenting / auditable.
CREATE TABLE IF NOT EXISTS raw_cache (
    source_name TEXT, source_url TEXT, retrieved_at TEXT,
    sha256 TEXT, payload TEXT
);
CREATE TABLE IF NOT EXISTS source_log (
    source_name TEXT, source_url TEXT, retrieved_at TEXT,
    record_count INTEGER, note TEXT
);
"""


class Store:
    def __init__(self, db_path: str | Path = ":memory:"):
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(self.db_path)
        self.con.execute(SCHEMA)

    # -- generic ----------------------------------------------------------
    def close(self) -> None:
        self.con.close()

    def count(self, table: str) -> int:
        return self.con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]

    def log_source(self, source_name: str, source_url: str, retrieved_at: str,
                   record_count: int, note: str = "") -> None:
        self.con.execute(
            "INSERT INTO source_log VALUES (?,?,?,?,?)",
            [source_name, source_url, retrieved_at, record_count, note],
        )

    # -- inserts (typed; provenance enforced by the models) ---------------
    def add_legislators(self, rows: Iterable[Legislator]) -> int:
        n = 0
        for r in rows:
            p = r.provenance
            self.con.execute(
                "INSERT OR REPLACE INTO legislators VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [r.person_id, r.full_name, r.first, r.middle, r.last, r.suffix,
                 r.chamber, r.district, r.party, r.hometown, r.first_elected,
                 r.years_served, r.occupation, json.dumps(r.committees),
                 r.is_former, p.source_name, p.source_url, p.retrieved_at.isoformat()],
            )
            for v in r.name_variants:
                self.con.execute(
                    "INSERT INTO name_variants VALUES (?,?,?)",
                    [r.person_id, v, "generated"],
                )
            n += 1
        return n

    def add_cannabis_entities(self, rows: Iterable[CannabisEntity]) -> int:
        n = 0
        for r in rows:
            p = r.provenance
            self.con.execute(
                "INSERT OR REPLACE INTO cannabis_entities VALUES (?,?,?,?,?,?,?,?)",
                [r.entity_id, r.name, r.entity_type, r.license_type, r.status,
                 p.source_name, p.source_url, p.retrieved_at.isoformat()],
            )
            n += 1
        return n

    def add_cannabis_persons(self, rows: Iterable[CannabisPerson]) -> int:
        n = 0
        for r in rows:
            p = r.provenance
            self.con.execute(
                "INSERT OR REPLACE INTO cannabis_persons VALUES (?,?,?,?,?,?,?,?,?)",
                [r.cp_id, r.full_name, r.role, r.credential_type, r.entity_name,
                 r.source_kind, p.source_name, p.source_url, p.retrieved_at.isoformat()],
            )
            n += 1
        return n

    def add_contributions(self, rows: Iterable[Contribution]) -> int:
        n = 0
        for r in rows:
            p = r.provenance
            self.con.execute(
                "INSERT OR REPLACE INTO contributions VALUES (?,?,?,?,?,?,?,?,?,?)",
                [r.contrib_id, r.contributor_name, r.employer, r.occupation,
                 r.amount, r.date, r.recipient_committee,
                 p.source_name, p.source_url, p.retrieved_at.isoformat()],
            )
            n += 1
        return n

    def add_lobbyists(self, rows: Iterable[Lobbyist]) -> int:
        n = 0
        for r in rows:
            p = r.provenance
            self.con.execute(
                "INSERT OR REPLACE INTO lobbyists VALUES (?,?,?,?,?,?,?,?,?)",
                [r.lobbyist_id, r.communicator_name, r.client_name, r.is_cannabis,
                 r.registration_year, r.hometown, p.source_name, p.source_url,
                 p.retrieved_at.isoformat()],
            )
            n += 1
        return n

    def add_sfi(self, rows: Iterable[SFIFiling]) -> int:
        n = 0
        for r in rows:
            p = r.provenance
            self.con.execute(
                "INSERT OR REPLACE INTO sfi VALUES (?,?,?,?,?,?,?,?)",
                [r.filing_id, r.legislator_name, r.filing_year,
                 r.spouse_employer, r.associated_business,
                 p.source_name, p.source_url, p.retrieved_at.isoformat()],
            )
            n += 1
        return n

    def add_matches(self, rows: Iterable[Match]) -> int:
        n = 0
        for r in rows:
            self.con.execute(
                "INSERT INTO matches VALUES (?,?,?,?,?,?,?,?)",
                [r.person_id, r.ref_type, r.ref_id, r.ref_label, r.confidence,
                 r.explanation, r.score, r.is_family_lead],
            )
            n += 1
        return n

    def add_findings(self, rows: Iterable[Finding]) -> int:
        n = 0
        for r in rows:
            self.con.execute(
                "INSERT INTO findings VALUES (?,?,?,?,?,?,?,?,?,?)",
                [r.person_id, r.person_name, r.category, r.status, r.confidence,
                 r.priority, r.legal_basis, r.explanation,
                 json.dumps(r.citations), r.is_family_lead],
            )
            n += 1
        return n

    # -- reads ------------------------------------------------------------
    def fetch_dicts(self, sql: str, params: list[Any] | None = None) -> list[dict]:
        cur = self.con.execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
