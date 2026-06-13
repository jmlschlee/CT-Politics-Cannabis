#!/usr/bin/env python3
"""CTCannabisPoliticalCheck — Connecticut Legislature & Municipal Cannabis
Conflict-of-Interest Screening.

A screening aid for humans, NOT an automated accusation engine. It cross-references
CT legislators (and town officials) against cannabis-industry connections from
official public sources, attaches a source + confidence tier to every potential
link, and routes anything touching a family member or below CONFIRMED to a human
review queue.

Run it (LIVE ONLY — this tool never uses synthetic/demo data):

    python3 CTCannabisPoliticalCheck.py            # LIVE run against real public sources
    python3 CTCannabisPoliticalCheck.py --no-municipal --no-downloads

Each run writes a NEW, never-overwritten PDF:

    reports/CTCannabisPoliticalCheck_<N>.pdf      (preserved here, N starts at 1)
    ~/Downloads/CTCannabisPoliticalCheck_<N>.pdf  (copied to the top of Downloads)

plus the working tracker, markdown report, review-queue CSVs, and the DuckDB store
in out/. The PDF carries live, clickable source citations and a numbered References
appendix.

CT cannabis context: MEDICAL legalized 2012 (PA 12-55), ADULT-USE 2021 (RERACA).
The full historical legislator roster is collected, but cross-referencing is scoped
to members serving 2012+ (a pre-2012 legislator cannot have a cannabis conflict).
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make `src` importable whether run from the repo root or elsewhere.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import config                      # noqa: E402
from src.pipeline import Pipeline                  # noqa: E402
from src.municipal import MunicipalPipeline        # noqa: E402
from src.report import finalize_report, DISPLAY_NAME  # noqa: E402


def _log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="CTCannabisPoliticalCheck", description=DISPLAY_NAME)
    ap.add_argument("--refresh-cache", action="store_true",
                    help="re-pull live sources instead of using the cache")
    ap.add_argument("--no-municipal", action="store_true",
                    help="skip the town/municipal layer")
    ap.add_argument("--no-downloads", action="store_true",
                    help="do not copy the numbered report to ~/Downloads")
    ap.add_argument("--since-year", type=int, default=None,
                    help="cannabis-era cutoff for cross-referencing (default 2012)")
    args = ap.parse_args(argv)

    # LIVE ONLY. This is a journalistic investigative tool: it cross-references real
    # CT officials against real public records and NEVER fabricates or uses synthetic/
    # demo data. There is no offline/fixture mode for report generation.
    cfg = config()
    _log(f"{DISPLAY_NAME} — LIVE (real public sources only; never synthetic data)")

    result = Pipeline(offline=False, refresh=args.refresh_cache,
                      since_year=args.since_year).run()
    _log(f"legislators in roster: {result.counts['legislators']:,} "
         f"({result.counts['current']} current / {result.counts['former']} former)")
    _log(f"cannabis-era members cross-referenced (2012+): "
         f"{result.counts.get('cross_referenced', 0)}")
    _log(f"cannabis principals/agents resolved from the registry: "
         f"{result.counts.get('cannabis_persons', 0)}")
    _log(f">> LEGISLATOR<->CANNABIS LEADS (verify): "
         f"{result.counts.get('legislator_cannabis_leads', 0)}")
    for d in result.legislator_cannabis_leads:
        _log(f"   [{d['confidence']}] {d['person']} ({d['party']},{d['district_or_town']})"
             f" ~ {d['cannabis_person']} / {d['cannabis_entity']}")
    _log(f"published findings: {result.counts['published']} · "
         f"review queue: {result.counts['review_queue']} · "
         f"recusals: {result.counts['recusals']}")

    municipal = None
    if not args.no_municipal:
        municipal = MunicipalPipeline(offline=False,
                                      refresh=args.refresh_cache).run()
        m = municipal.counts
        _log(f"municipal: {m['host_towns']} host towns · {m['facilities']} "
             f"facilities · CONFIRMED {m['confirmed']} / UNCONFIRMED "
             f"{m['unconfirmed']} / UNSUPPORTED {m['unsupported']} / CONTEXT "
             f"{m['context']} · {m['substantial_conflicts']} substantial conflict(s)")

    rep = finalize_report(result, cfg, municipal=municipal,
                          push_to_downloads=not args.no_downloads)
    _log(f"REPORT #{rep['number']} written: {rep['report_pdf']}")
    if rep["downloads_pdf"]:
        _log(f"pushed to top of Downloads: {rep['downloads_pdf']}")
    _log("other outputs: " + ", ".join(
        f"{k}={v}" for k, v in rep["paths"].items() if k != "findings_pdf" and v))
    _log("Reminder: this is a screening aid. Nothing in the review queue is a "
         "confirmed conflict until a human verifies it against a primary source.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
