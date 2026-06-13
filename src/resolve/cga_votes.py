"""CT General Assembly roll-call votes on cannabis bills (V2 #5).

Pulls the ACTUAL per-legislator roll-call tallies from cga.ct.gov for the landmark
cannabis bills, so a connected legislator's vote is a hard fact (YEA / NAY / ABSENT)
rather than a web-sourced impression. For each bill we:

  1. read the bill-status page and collect its VOTE PDF links,
  2. parse each roll-call PDF (Y/N/A + district + NAME),
  3. keep the FINAL-PASSAGE vote per chamber (the one with the most members voting),
  4. expose `legislator_vote(name)` to look up how a given member voted.

Plus `recusal_search()` — a per-legislator web check for a cannabis recusal/ethics
record, returning FOUND RECUSAL / NO RECUSAL FOUND / INSUFFICIENT DATA.

cga.ct.gov uses a state TLS chain this environment doesn't bundle, so the fetch
disables verification for that host only (read-only public records). LIVE-only;
offline returns the empty/undetermined shape so tests stay deterministic.
"""
from __future__ import annotations

import json
import re

from ..config import cache_dir
from ..normalize import canonical, parse_name, surname_key

# Landmark CT cannabis bills (year, bill number, short title, era).
CANNABIS_BILLS = [
    (2021, "1201", "RERACA — adult-use cannabis legalization (PA 21-1)", "adult-use"),
    (2012, "5389", "Medical marijuana / palliative use (PA 12-55)", "medical"),
]

_STATUS_URL = ("https://www.cga.ct.gov/asp/cgabillstatus/cgabillstatus.asp"
               "?selBillType=Bill&bill_num={num}&which_year={yr}")
_HOST = "https://www.cga.ct.gov"
_VOTE_RE = re.compile(r"/\d{4}/VOTE/[HS]/PDF/[^\"']+\.PDF", re.I)
# Unified roll-call row: vote letter, OPTIONAL district number (Senate prints it,
# House does not), then the NAME. Senate rows are full names ("KEVIN C. KELLY");
# House rows are surname-only, sometimes with a disambiguating initial ("WOOD, K.").
_PAIR_RE = re.compile(
    r"\b([YNAX])\s+(?:\d{1,3}\s+)?([A-Z][A-Za-z.,'\- ]*?)(?=\s+[YNAX]\s|\n|$)")
_SEQ_RE = re.compile(r"/\d{4}[HS]V-(\d+)-", re.I)


def _surname_initial(name: str) -> tuple[str, str]:
    """(canonical surname, first-name initial) from a roll-call name in either the
    Senate 'FIRST M. LAST' or House 'LAST' / 'LAST, F.' layout."""
    name = re.sub(r"\s+", " ", name).strip().strip(",")
    if "," in name:                       # House "WOOD, K." -> surname WOOD, initial K
        last, _, rest = name.partition(",")
        return canonical(last), canonical(rest.strip())[:1]
    parts = name.split()
    if len(parts) == 1:                   # House "ABERCROMBIE" -> surname only
        return canonical(parts[0]), ""
    return canonical(parts[-1]), canonical(parts[0])[:1]  # Senate "FIRST .. LAST"


def _client():
    import httpx
    return httpx.Client(timeout=45, follow_redirects=True, verify=False,
                        headers={"User-Agent": "Mozilla/5.0 (CTCannabisPoliticalCheck)"})


def _parse_rollcall_pdf(content: bytes) -> dict:
    """Parse one roll-call PDF -> {voters: [{surname, initial, vote, raw}], tallies}."""
    import fitz
    doc = fitz.open(stream=content, filetype="pdf")
    txt = re.sub(r"[ \t]+", " ", "\n".join(p.get_text() for p in doc))
    voters: list[dict] = []
    for letter, name in _PAIR_RE.findall(txt):
        nm = re.sub(r"\s+", " ", name).strip().strip(",")
        if len(nm) < 3 or nm in ("AS", "PDF"):
            continue
        sur, ini = _surname_initial(nm)
        if sur:
            voters.append({"surname": sur, "initial": ini,
                           "vote": letter.upper(), "raw": nm})
    yea = sum(1 for v in voters if v["vote"] == "Y")
    nay = sum(1 for v in voters if v["vote"] == "N")
    absent = sum(1 for v in voters if v["vote"] in ("A", "X"))
    return {"voters": voters, "yea": yea, "nay": nay, "absent": absent,
            "total": len(voters)}


class CgaRollCalls:
    def __init__(self, *, offline: bool = False, refresh: bool = False):
        self.offline = offline
        self.refresh = refresh
        self.bills: list[dict] = []   # one per (bill, chamber) final passage
        self._loaded = False

    def _cache_path(self, year: int, num: str):
        d = cache_dir() / "cga"
        d.mkdir(parents=True, exist_ok=True)
        return d / f"rollcall_{year}_{num}.json"

    def _fetch_bill(self, year: int, num: str, title: str, era: str) -> list[dict]:
        if self.offline:
            return []   # offline is inert — never read the live cache (deterministic)
        cp = self._cache_path(year, num)
        if cp.exists() and not self.refresh:
            try:
                return json.loads(cp.read_text())
            except Exception:  # noqa: BLE001
                pass
        out: list[dict] = []
        try:
            cli = _client()
            status = cli.get(_STATUS_URL.format(num=num, yr=year)).text
            links = sorted(set(_VOTE_RE.findall(status)))
            best: dict[str, dict] = {}   # chamber -> final-passage roll-call
            best_seq: dict[str, int] = {}
            for ln in links:
                chamber = "Senate" if "/S/" in ln.upper() else "House"
                sm = _SEQ_RE.search(ln)
                seq = int(sm.group(1)) if sm else 0
                try:
                    rc = _parse_rollcall_pdf(cli.get(_HOST + ln).content)
                except Exception:  # noqa: BLE001
                    continue
                if rc["total"] == 0:
                    continue
                # FINAL PASSAGE = the highest sequence number in the chamber (amendment
                # votes are taken before the vote on the bill as a whole).
                if chamber not in best or seq > best_seq[chamber]:
                    rc.update(chamber=chamber, url=_HOST + ln, sequence=seq)
                    best[chamber] = rc
                    best_seq[chamber] = seq
            for chamber, rc in best.items():
                rc.update(year=year, bill=f"{'SB' if chamber=='Senate' else 'HB'} {num}",
                          bill_num=num, title=title, era=era)
                out.append(rc)
        except Exception:  # noqa: BLE001
            out = []
        if out:
            cp.write_text(json.dumps(out))
        return out

    def load(self):
        if self._loaded:
            return self
        for year, num, title, era in CANNABIS_BILLS:
            self.bills.extend(self._fetch_bill(year, num, title, era))
        self._loaded = True
        return self

    def legislator_vote(self, full_name: str) -> list[dict]:
        """How `full_name` voted on each cannabis bill (match by surname + initial)."""
        self.load()
        p = parse_name(full_name)
        sk, fi = canonical(p.last), canonical(p.first)[:1]
        if not sk:
            return []
        out = []
        for b in self.bills:
            cand = [v for v in b.get("voters", []) if v["surname"] == sk]
            # disambiguate same-surname members by first initial when the roll-call
            # printed one; if still ambiguous, skip (don't guess a member's vote).
            if len(cand) > 1 and fi:
                cand = [v for v in cand if not v["initial"] or v["initial"] == fi] or cand
            if len(cand) != 1:
                continue
            v = cand[0]
            out.append(dict(
                year=b["year"], bill=b["bill"], title=b["title"],
                era=b["era"], chamber=b["chamber"],
                vote={"Y": "YEA", "N": "NAY", "A": "ABSENT",
                      "X": "ABSENT"}.get(v["vote"], v["vote"]),
                tally=f"{b['yea']}-{b['nay']} (absent {b['absent']})",
                url=b["url"]))
        return out


def recusal_search(legislator_name: str, *, offline: bool = False) -> dict:
    """Per-legislator cannabis recusal/ethics check. FOUND RECUSAL / NO RECUSAL FOUND
    / INSUFFICIENT DATA, with any sourcing."""
    if offline:
        return {"status": "INSUFFICIENT DATA", "sources": [],
                "note": "recusal search is live-only"}
    try:
        from .web_search import web_search
    except Exception:  # noqa: BLE001
        return {"status": "INSUFFICIENT DATA", "sources": []}
    pos = re.compile(r"\brecus|step(?:ped)?\s+aside|did not vote due to|conflict of "
                     r"interest", re.I)
    sources, hits, any_result = [], 0, 0
    for q in (f"{legislator_name} cannabis recusal conflict of interest",
              f"{legislator_name} recused cannabis vote"):
        for r in web_search(q, max_results=6, offline=False):
            any_result += 1
            if pos.search(r.text) and re.search(r"cannabis|marijuana", r.text, re.I):
                hits += 1
                if r.url not in sources:
                    sources.append(r.url)
    if hits:
        status = "FOUND RECUSAL"
    elif any_result:
        status = "NO RECUSAL FOUND"
    else:
        status = "INSUFFICIENT DATA"
    return {"status": status, "sources": sources[:3]}
