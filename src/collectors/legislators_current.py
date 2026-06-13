"""Current CT General Assembly members (House + Senate).

Live source: data.ct.gov "Current and Historical Connecticut State Legislators"
(h2b3-nyih) — one dataset holds the full roster back to 1915; this collector loads
all of it and computes is_former from years_served."""
from __future__ import annotations

import re

from ..models import Legislator
from ..normalize import canonical, name_variants, parse_name
from .base import Collector, provenance_for


def roster_to_legislator(d: dict, source_name: str, default_url: str,
                         is_former: bool = False) -> Legislator:
    parts = parse_name(d["full_name"])
    variants = name_variants(d["full_name"], maiden=d.get("maiden"))
    return Legislator(
        person_id=d["person_id"],
        full_name=d["full_name"],
        first=parts.first, middle=parts.middle, last=parts.last, suffix=parts.suffix,
        chamber=d.get("chamber"),
        district=str(d.get("district", "")),
        party=d.get("party", ""),
        hometown=d.get("hometown", d.get("town", "")),
        first_elected=d.get("first_elected"),
        years_served=d.get("years_served", ""),
        occupation=d.get("occupation", ""),
        committees=d.get("committees", []),
        is_former=d.get("is_former", is_former),
        name_variants=variants,
        provenance=provenance_for(source_name, d.get("source_url", default_url)),
    )


def _na(v) -> str:
    v = (v or "").strip()
    return "" if v.lower() in ("no data", "n/a", "none") else v


def _years(years_served: str) -> list[int]:
    return sorted(int(y) for y in re.findall(r"\b(1[89]\d\d|20\d\d)\b", years_served or ""))


def socrata_row_to_dict(r: dict, dataset_url: str, latest_year: int,
                        within: int) -> dict:
    """`latest_year` is the most recent year present in the dataset (the snapshot's
    current session); a member is CURRENT if they served within `within` years of
    it, else FORMER. This tracks the data, not the wall clock."""
    first, last = _na(r.get("first_name")), _na(r.get("last_name"))
    mid = _na(r.get("middle_name_initial"))
    suffix = _na(r.get("suffix_prefix_honorifics"))
    town = _na(r.get("town"))
    full = " ".join(x for x in [first, (mid + "." if mid and len(mid) == 1 else mid),
                                last] if x).strip()
    yrs = _years(r.get("years_served", ""))
    deceased = bool(_na(r.get("date_of_death")))
    is_former = deceased or (bool(yrs) and max(yrs) < latest_year - within)
    chamber = _na(r.get("chamber")) or None
    if chamber not in ("House", "Senate"):
        chamber = None
    pid = "cga-" + "-".join(canonical(x).replace(" ", "_") for x in
                            [last, first, town, str(yrs[0] if yrs else "")] if x)
    return dict(
        person_id=pid or f"cga-{abs(hash(full))}", full_name=full or "(unknown)",
        chamber=chamber, party=_na(r.get("political_affiliation")), town=town,
        years_served=r.get("years_served", ""),
        first_elected=yrs[0] if yrs else None, is_former=is_former,
        source_url=dataset_url,
    )


class LegislatorsCurrentCollector(Collector):
    source_name = "legislators_current"
    fixture_name = "legislators_current"

    def fetch_live(self) -> list:
        from .live_socrata import socrata_get
        sc = self.src["socrata"]
        rows = socrata_get(sc["domain"], sc["dataset_id"])
        url = f"https://{sc['domain']}/d/{sc['dataset_id']}"
        within = self.src.get("current_within_years", 1)
        # Most recent year the dataset knows about = this snapshot's "current" session.
        cap = self.src.get("current_year", 2026)
        all_years = [y for r in rows for y in _years(r.get("years_served", "")) if y <= cap]
        latest_year = max(all_years) if all_years else cap
        mapped = [socrata_row_to_dict(r, url, latest_year, within) for r in rows]
        # de-dup on person_id (multi-term members appear once)
        seen, out = set(), []
        for m in mapped:
            if m["person_id"] in seen:
                continue
            seen.add(m["person_id"])
            out.append(m)
        return out

    def parse(self, raw) -> list[Legislator]:
        url = self.src.get("base_url", "https://www.cga.ct.gov")
        return [roster_to_legislator(d, self.source_name, url, is_former=False)
                for d in raw]
