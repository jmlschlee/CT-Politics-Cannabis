"""SEEC eCRIS campaign-finance collector — cannabis money into CT politics.

Campaign finance is NOT on data.ct.gov (no Socrata bulk API); it lives in the
State Elections Enforcement Commission's eCRIS portal. Per the V2 mandate
("don't stop at 'no bulk API' — use the live portal"), this collector drives the
public eCRIS *contribution search* directly:

  GET  SearchingContribution.aspx            -> grab the ASP.NET __VIEWSTATE
  POST txtEmployerName / txtContributorName   -> the gvSearchResult grid
       + btnSearch

Each result row gives the donor, their EMPLOYER (the cannabis-industry link),
city, the RECIPIENT committee + office sought + district (the legislator link),
amount, date, and party — every field public record. Results are cached per query
under data/cache/seec/ so re-runs are instant. LIVE-only: offline loads a small
deterministic fixture so tests/demos never hit the network.

We search by EMPLOYER for each cannabis business (catches every employee of an
operator who donated) and by CONTRIBUTOR for the resolved cannabis principals and
the connected legislators themselves. The pipeline then ties each contribution to
a specific legislator by committee/surname.

NOTE: this is a SEPARATE, live collector from the legacy fixture-only
`campaign_finance.CampaignFinanceCollector` used by the base pipeline.
"""
from __future__ import annotations

import html
import json
import re
import time
from hashlib import sha1

from ..config import cache_dir
from ..models import CampaignContribution, Provenance

_SEARCH_URL = "https://seec.ct.gov/eCrisReporting/SearchingContribution.aspx"
_PREFIX = "ctl00$ContentPlaceHolder1$"
_GRID_ID = "ctl00_ContentPlaceHolder1_gvSearchResult"
_UA = "Mozilla/5.0 (CTCannabisPoliticalCheck; CT cannabis political-conflict research)"

# Office-sought values that mean the recipient is a STATE LEGISLATIVE candidate.
LEGISLATIVE_OFFICES = {"state senator", "state representative"}


def _hidden(name: str, page: str) -> str:
    m = re.search(rf'id="{re.escape(name)}"[^>]*value="([^"]*)"', page)
    return html.unescape(m.group(1)) if m else ""


def _iso(s: str) -> str:
    """MM/DD/YYYY -> ISO YYYY-MM-DD; pass through anything else."""
    s = (s or "").strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else s


def _amount(s: str) -> float:
    s = re.sub(r"[^0-9.\-]", "", (s or "").strip())
    try:
        return float(s) if s else 0.0
    except ValueError:
        return 0.0


def _cell_text(cell_html: str) -> str:
    # eCRIS grid cells carry inter-character markup, so tags must be stripped to
    # EMPTY (not a space) or every name comes out spaced ("E s t h e r"). Real word
    # spacing is preserved by the source; we only collapse runs of whitespace.
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(cell_html))).strip()


def parse_grid(page: str) -> list[dict]:
    """Parse the gvSearchResult grid into a list of header->value dicts."""
    tm = re.search(rf'<table[^>]*id="{_GRID_ID}".*?</table>', page, re.S)
    seg = tm.group(0) if tm else page
    headers = [_cell_text(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", seg, re.S)]
    if not headers:
        return []
    rows: list[dict] = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", seg, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(cells) < len(headers):
            continue
        vals = [_cell_text(c) for c in cells[: len(headers)]]
        rows.append(dict(zip(headers, vals)))
    return rows


def normalize_entity(name: str) -> str:
    """Normalize a business name for dedup + as the employer search term: drop the
    corporate suffix so 'Curaleaf CT, LLC' and 'Curaleaf' collapse to one query."""
    n = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower())
    n = re.sub(r"\b(llc|inc|corp|co|ltd|lp|llp|the|cannabis|ct|connecticut|"
               r"holdings?|company|group|ventures?|dispensary|management)\b", " ", n)
    return re.sub(r"\s+", " ", n).strip()


class SeecContributionSearch:
    """Thin driver over the eCRIS contribution search ASP.NET form."""

    def __init__(self, *, offline: bool = False, refresh: bool = False,
                 delay: float = 0.8):
        self.offline = offline
        self.refresh = refresh
        self.delay = delay
        self.searches: list[str] = []   # audit log of every query actually run

    def _cache_path(self, key: str):
        d = cache_dir() / "seec"
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{key}.json"

    def search(self, *, employer: str = "", contributor: str = "",
               committee: str = "", since: str = "01/01/2012") -> list[dict]:
        """Run one contribution search; returns parsed grid rows (cached)."""
        qkey = sha1(f"e={employer}|c={contributor}|m={committee}|s={since}"
                    .lower().encode()).hexdigest()[:16]
        cp = self._cache_path(qkey)
        if cp.exists() and not self.refresh:
            try:
                return json.loads(cp.read_text())
            except Exception:  # noqa: BLE001
                pass
        if self.offline:
            return []
        try:
            import httpx
            cli = httpx.Client(timeout=60, follow_redirects=True,
                               headers={"User-Agent": _UA})
            page = cli.get(_SEARCH_URL).text
            form = {
                "__EVENTTARGET": "", "__EVENTARGUMENT": "", "__LASTFOCUS": "",
                "__VIEWSTATE": _hidden("__VIEWSTATE", page),
                "__VIEWSTATEGENERATOR": _hidden("__VIEWSTATEGENERATOR", page),
                "__EVENTVALIDATION": _hidden("__EVENTVALIDATION", page),
                "__VIEWSTATEENCRYPTED": "",
                f"{_PREFIX}txtContributorName": contributor,
                f"{_PREFIX}txtEmployerName": employer,
                f"{_PREFIX}txtCommittee": committee,
                f"{_PREFIX}txtCity": "",
                f"{_PREFIX}txtTransactionStartDate": since,
                f"{_PREFIX}txtTransactionEndDate": "",
                f"{_PREFIX}txtMinAmount": "", f"{_PREFIX}txtMaxAmount": "",
                f"{_PREFIX}btnSearch": "Search",
            }
            label = (f"employer={employer}" if employer else
                     f"contributor={contributor}" if contributor else
                     f"committee={committee}")
            self.searches.append(label)
            resp = cli.post(_SEARCH_URL, data=form)
            resp.raise_for_status()
            rows = parse_grid(resp.text)
            cp.write_text(json.dumps(rows))
            time.sleep(self.delay)
            return rows
        except Exception:  # noqa: BLE001
            return []


class SeecCampaignFinance:
    """Resolve cannabis-linked campaign contributions from eCRIS.

    Inputs are the cannabis business names (employer search) and a set of person
    names — resolved cannabis principals + connected legislators (contributor
    search). Returns CampaignContribution records, deduplicated by receipt id.
    """

    def __init__(self, *, offline: bool = False, refresh: bool = False,
                 employer_budget: int = 80, contributor_budget: int = 40):
        self.offline = offline
        self.refresh = refresh
        self.employer_budget = employer_budget
        self.contributor_budget = contributor_budget
        self.driver = SeecContributionSearch(offline=offline, refresh=refresh)
        self.last_status = ("", 0, "")
        self.capped = {"employers": 0, "contributors": 0}

    def _fixture(self) -> list[CampaignContribution]:
        from ..config import ROOT
        fx = ROOT / "tests" / "fixtures" / "campaign_contributions.json"
        if not fx.exists():
            return []
        prov = Provenance(source_name="seec_ecris",
                          source_url=_SEARCH_URL + " (fixture)")
        return [CampaignContribution(provenance=prov, **r)
                for r in json.loads(fx.read_text())]

    def _row_to_model(self, row: dict, matched_by: str,
                      prov: Provenance):
        rid = (row.get("Receipt ID") or row.get("Root Contrib ID") or "").strip()
        donor = (row.get("Received From") or "").strip()
        if not rid or not donor:
            return None
        return CampaignContribution(
            receipt_id=rid, contributor_name=donor,
            employer=(row.get("Employer") or "").strip(),
            occupation=(row.get("Occupation") or "").strip(),
            city=(row.get("City") or "").strip(),
            state=(row.get("State") or "").strip(),
            amount=_amount(row.get("Amount")),
            date=_iso(row.get("Transaction Date")),
            recipient_committee=re.sub(r"\s*\(SEEC\d+\)\s*$", "",
                                       (row.get("Committee") or "")).strip(),
            office_sought=(row.get("Office Sought") or "").strip(),
            district=(row.get("District") or "").strip(),
            committee_type=(row.get("Committee Type") or "").strip(),
            party=(row.get("Committee Party Affiliation") or "").strip(),
            election_year=(row.get("Election Year") or "").strip(),
            receipt_type=(row.get("Receipt Type") or "").strip(),
            matched_by=matched_by, provenance=prov)

    def collect(self, business_names: list[str],
                person_names: list[str] | None = None) -> list[CampaignContribution]:
        if self.offline:
            out = self._fixture()
            self.last_status = ("fixture", len(out),
                                "eCRIS is live-only; offline uses the fixture")
            return out
        prov = Provenance(source_name="seec_ecris", source_url=_SEARCH_URL)
        by_receipt: dict[str, CampaignContribution] = {}

        # --- employer searches (one per distinct normalized business name) ----
        seen_emp: set[str] = set()
        emp_terms: list[str] = []
        for b in business_names:
            term = normalize_entity(b)
            if len(term) < 4 or term in seen_emp:
                continue
            seen_emp.add(term)
            emp_terms.append(term)
        if len(emp_terms) > self.employer_budget:
            self.capped["employers"] = len(emp_terms) - self.employer_budget
            emp_terms = emp_terms[: self.employer_budget]
        for term in emp_terms:
            for row in self.driver.search(employer=term):
                m = self._row_to_model(row, f"employer:{term}", prov)
                if m:
                    by_receipt.setdefault(m.receipt_id, m)

        # --- contributor searches (principals + connected legislators) --------
        seen_p: set[str] = set()
        p_terms: list[str] = []
        for p in (person_names or []):
            key = re.sub(r"\s+", " ", (p or "").strip().lower())
            if len(key) < 5 or key in seen_p:
                continue
            seen_p.add(key)
            p_terms.append(p.strip())
        if len(p_terms) > self.contributor_budget:
            self.capped["contributors"] = len(p_terms) - self.contributor_budget
            p_terms = p_terms[: self.contributor_budget]
        for p in p_terms:
            for row in self.driver.search(contributor=p):
                m = self._row_to_model(row, f"contributor:{p}", prov)
                if m:
                    by_receipt.setdefault(m.receipt_id, m)

        out = list(by_receipt.values())
        n_emp, n_con = len(emp_terms), len(p_terms)
        self.last_status = (
            "live" if out else "live-empty", len(out),
            f"{n_emp} employer + {n_con} contributor searches"
            + (f"; CAPPED {self.capped['employers']} employers / "
               f"{self.capped['contributors']} contributors not searched"
               if any(self.capped.values()) else ""))
        return out


def is_legislative(contribution) -> bool:
    """True when the recipient is a state legislative candidate committee."""
    return (contribution.office_sought or "").strip().lower() in LEGISLATIVE_OFFICES
