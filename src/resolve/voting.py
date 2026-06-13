"""Cannabis legislative voting + timeline analysis for connected legislators.

CT cannabis eras: MEDICAL 2012 (PA 12-55), ADULT-USE 2021 (PA 21-1 / SB 1201).
For each legislator with a cannabis connection this builds:
  * their voting STANCE on cannabis (web-sourced), and
  * a TIMELINE comparing political service vs cannabis involvement, so a reader can
    see whether the cannabis interest arose before / during / after their service.

Full per-bill roll-call tallies live on cga.ct.gov as HTML/PDF vote pages and are a
larger integration; this surfaces the stance + timeline (the high-value context) and
flags where a precise roll-call lookup is still needed.
"""
from __future__ import annotations

import re

from .web_search import web_search

_SUPPORT = re.compile(r"\b(support|voted for|backed|co-?sponsor|champion|in favor|"
                      r"yes vote|advocat)\w*", re.I)
_OPPOSE = re.compile(r"\b(oppos|voted against|against legaliz|fought against|"
                     r"no vote|vocal opponent|criticiz)\w*", re.I)
_CANNABIS = re.compile(r"cannabis|marijuana", re.I)
_YEAR = re.compile(r"\b(20[0-2]\d)\b")


def _years(years_served: str) -> list[int]:
    return sorted({int(y) for y in re.findall(r"\b(19\d\d|20\d\d)\b", years_served or "")})


def cannabis_voting_record(legislator_name: str, years_served: str,
                           cannabis_date: str = "", *, offline: bool = False) -> dict:
    """Return {stance, quote, sources, timeline, eras}."""
    yrs = _years(years_served)
    served_from = yrs[0] if yrs else None
    served_to = yrs[-1] if yrs else None
    eras = []
    if any(2012 <= y <= 2020 for y in yrs):
        eras.append("Medical era (2012+)")
    if any(y >= 2021 for y in yrs):
        eras.append("Adult-use era (2021+)")

    stance, quote, sources = "undetermined", "", []
    sup = opp = 0
    for q in (f'{legislator_name} cannabis marijuana vote',
              f'{legislator_name} cannabis legalization position'):
        for r in web_search(q, max_results=6, offline=offline):
            t = r.text
            if not _CANNABIS.search(t):
                continue
            if _OPPOSE.search(t):
                opp += 1
                if not quote:
                    quote, = (f"{r.title} — “{r.snippet[:160]}”",)
                    sources.append(r.url)
            elif _SUPPORT.search(t):
                sup += 1
                if not quote:
                    quote = f"{r.title} — “{r.snippet[:160]}”"
                    sources.append(r.url)
    if opp and opp >= sup:
        stance = "OPPOSED cannabis legislation as a legislator"
    elif sup:
        stance = "SUPPORTED cannabis legislation as a legislator"

    # timeline
    cy = ""
    if cannabis_date:
        m = re.match(r"(\d{4})", cannabis_date)
        cy = m.group(1) if m else ""
    timeline = []
    if served_from:
        timeline.append((served_from,
                         f"Took office (served {served_from}–{served_to})"))
    if stance != "undetermined" and served_to:
        timeline.append((served_to, stance + " (during service)"))
    if cy:
        rel = ("AFTER leaving office" if served_to and int(cy) > served_to
               else "DURING service" if served_to and served_from and
               served_from <= int(cy) <= served_to else "")
        timeline.append((int(cy), f"Cannabis involvement on record (registered "
                                  f"{cannabis_date}) — {rel}".rstrip(" —")))
    timeline.sort()
    return {"stance": stance, "quote": quote, "sources": sorted(set(sources)),
            "timeline": timeline, "eras": eras,
            "served_from": served_from, "served_to": served_to,
            "note": ("Stance is web-sourced; precise per-bill roll-call tallies "
                     "(cga.ct.gov vote pages) are a further integration.")}
