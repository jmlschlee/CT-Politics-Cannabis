"""DCP eLicense cannabis-credential roster scraper.

Pulls the PRE-BUILT public rosters from elicense.ct.gov that name the INDIVIDUALS
tied to each cannabis license — Establishment Backers and Key Employees (and other
credential categories) — which are NOT on data.ct.gov. Each roster row gives a
person's name, CITY (for town-matching), license #, the cannabis business they are
tied to, and real EFFECTIVE / EXPIRATION dates.

Flow (ASP.NET): GET GenerateRoster.aspx -> POST the credential checkbox + Continue
-> read the generated roster Idnt -> GET FileDownload.aspx?Idnt=..&Type=CSV.

Rank-and-file "Cannabis Establishment Employee Registration" (ckbRoster76) is
intentionally EXCLUDED per scope. Results are cached (the CSVs are small) so
re-runs are instant.
"""
from __future__ import annotations

import csv
import io
import re
import time

from ..config import cache_dir
from ..models import CannabisPerson, Provenance

_BASE = "https://www.elicense.ct.gov/Lookup"
_GEN = f"{_BASE}/GenerateRoster.aspx"
_DL = f"{_BASE}/FileDownload.aspx"
_PREFIX = "ctl00$MainContentPlaceHolder$"

# Cannabis credential rosters that name INDIVIDUALS or establishments we want.
# (ckbRoster76 = rank-and-file employee registration -> EXCLUDED.)
ROSTERS = {
    "ckbRoster75": ("Cannabis Establishment Backer", "backer"),
    "ckbRoster77": ("Cannabis Establishment Key Employee", "key_employee"),
}
# Source/provenance URL recorded on every record.
_SRC = _GEN


def _hidden(name: str, html: str) -> str:
    m = re.search(rf'id="{re.escape(name)}"[^>]*value="([^"]*)"', html)
    return m.group(1) if m else ""


def _norm_date(s: str) -> str:
    """eLicense dates are MM/DD/YYYY -> ISO YYYY-MM-DD (record date)."""
    s = (s or "").strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else s


class ELicenseRosterScraper:
    def __init__(self, *, offline: bool = False, refresh: bool = False):
        self.offline = offline
        self.refresh = refresh
        self.last_status = ("", 0, "")

    def _cache_csv(self, key: str):
        d = cache_dir() / "elicense"
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{key}.csv"

    def _download_roster(self, ckb: str) -> str:
        """Return the roster CSV text (cached)."""
        cp = self._cache_csv(ckb)
        if cp.exists() and not self.refresh:
            return cp.read_text(encoding="utf-8", errors="replace")
        if self.offline:
            return ""
        import httpx
        s = httpx.Client(timeout=120, follow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0 (ct-cannabis-conflicts)"})
        html = s.get(_GEN).text
        data = {
            "__VIEWSTATE": _hidden("__VIEWSTATE", html),
            "__VIEWSTATEGENERATOR": _hidden("__VIEWSTATEGENERATOR", html),
            "__VIEWSTATEENCRYPTED": "",
            f"{_PREFIX}{ckb}": "on",
            f"{_PREFIX}btnRosterContinue": "Continue",
        }
        t = s.post(_GEN, data=data).text
        m = re.search(r"Selected~Roster(\d+)", t)
        if not m:
            return ""
        idnt = m.group(1)
        time.sleep(1.0)
        r = s.get(_DL, params={"Idnt": idnt, "Type": "CSV"})
        r.raise_for_status()
        text = r.text
        if "FIRST NAME" in text or "LICENSE" in text:
            cp.write_text(text, encoding="utf-8")
        return text

    def collect(self) -> list[CannabisPerson]:
        out: list[CannabisPerson] = []
        n_roster = 0
        if self.offline:
            # eLicense is a LIVE-only scrape; offline (fixture/demo) excludes it so
            # results stay deterministic and the live cache never leaks into tests.
            self.last_status = ("unavailable", 0,
                                "eLicense roster is live-only (not run offline)")
            return out
        prov = Provenance(source_name="dcp_elicense", source_url=_SRC)
        for ckb, (label, role) in ROSTERS.items():
            try:
                text = self._download_roster(ckb)
            except Exception:  # noqa: BLE001
                text = ""
            if not text.strip():
                continue
            # eLicense roster CSVs are TAB-delimited.
            rdr = csv.DictReader(io.StringIO(text), delimiter="\t")
            n_roster += 1
            for row in rdr:
                row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
                first, last = row.get("FIRST NAME", ""), row.get("LAST NAME", "")
                full = f"{first} {last}".strip()
                if not full:
                    continue
                business = row.get("Supervision", "") or row.get("SUPERVISION", "")
                lic = row.get("LICENSE", "")
                out.append(CannabisPerson(
                    cp_id=f"elic::{role}::{lic}::{full}",
                    full_name=full, role=role, credential_type=label,
                    entity_name=business, source_kind="dcp",
                    residence_city=row.get("CITY", "").title(),
                    license_type=label, license_number=lic,
                    registration_date=_norm_date(row.get("EFFECTIVE DATE", "")),
                    business_url=_SRC, provenance=prov))
        self.last_status = (
            "live" if (n_roster and not self.offline) else
            ("cache" if n_roster else "unavailable"), len(out),
            "" if n_roster else "eLicense roster scrape returned no data")
        return out
