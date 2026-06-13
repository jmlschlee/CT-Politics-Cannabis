# HANDOFF — CTCannabisPoliticalCheck (resume brief)

## ⭐ v1.2.0 — LIVE ONLY, NEVER SYNTHETIC DATA (2026-06-12)
This is a JOURNALISTIC INVESTIGATIVE TOOL. Accuracy/truth is the whole point. Hard rule:
**NEVER use synthetic/demo/fabricated data in any report.** The program is LIVE ONLY —
no `--offline`, no fixture-backed reports. `build_single_file.py` does NOT bundle
`tests/fixtures/`. Test fixtures exist ONLY to validate the engine in `make test`
(`Pipeline(offline=True)` in the 64 tests) and never reach a report. A real run takes
~4 min (reduced delays). The verified real output = report #32 (Art Linares VERIFIED,
all sections, real sourced links). Earlier false positives were ONLY in the (now
removed) offline demo fixtures that wrongly used real legislator names — fixed in 1.1.1,
mode removed in 1.2.0. Release: https://github.com/jmlschlee/CT-Politics-Cannabis/releases

## ⭐ RELEASE 1.0.0 SHIPPED (2026-06-12)
- **GitHub repo:** https://github.com/jmlschlee/CT-Politics-Cannabis (main = full project).
- **Release:** https://github.com/jmlschlee/CT-Politics-Cannabis/releases/tag/v1.0.0
  (id 338882234) — assets: 3 OS zips (macOS/Linux/Windows, identical content +
  run.sh/run.bat), `streamlit_app.py`, sample-report PDF.
- Pushed non-destructively (merged the repo's original LICENSE/Initial-commit; my
  README/v1.0 content kept). All 5 V2 items + the post-V2 fixes are in this release.
- **Streamlit:** deploy from repo `jmlschlee/CT-Politics-Cannabis`, branch `main`,
  main file `streamlit_app.py` (light theme pinned in `.streamlit/config.toml`).
- **Version single source:** `src/report/build.py::VERSION` (1.0.0) / `app_version()`.
- ⚠️ **ROTATE the GitHub PAT** that was pasted in chat — it was used only in inline
  push/curl URLs (never written to any committed file or `.git/config`).
- Post-V2 fixes in this release: §1/§2 Tier column widened (relabel made labels
  longer); EVERY findings row now shows a Verification line (sources or explicit "no
  primary source"); municipal Glassman pattern generalized to a CATEGORY across all
  host towns (§3a official-tie leads + §3b town-attorney chains + §3c roster).
- To cut a future release: bump `VERSION`, commit, `git push`, then create a release
  via the GitHub API with `git archive` zips (the repo is NOT self-contained — it's a
  package, so zips = the tracked tree + run scripts).



**What it is.** A reproducible Connecticut Cannabis Political Relationship Intelligence
tool / screening aid for humans (NOT an auto-accusation engine). It cross-references CT
legislators (and town officials) against cannabis-industry connections from official
public sources + live web research, actively RESOLVES each relationship, assigns a
confidence tier with evidence, and produces a numbered PDF.

- **Repo / cwd:** `/Users/josiahschlee/Downloads/ct-cannabis-conflicts/`
- **Entry file (the program):** `CTCannabisPoliticalCheck.py` (repo root)
- **Latest report:** #20 (and counting) — see `reports/` and `~/Downloads/`

## Run it
```bash
python3 CTCannabisPoliticalCheck.py            # LIVE (data.ct.gov + web); ~1.5–5 min
python3 CTCannabisPoliticalCheck.py --offline  # fixture demo (deterministic, fast)
python3 CTCannabisPoliticalCheck.py --refresh-cache   # re-verify (ignore caches)
make run | make run-offline | make test        # 41 tests
```
Each run writes a NEW, never-overwritten `reports/CTCannabisPoliticalCheck_<N>.pdf` and
copies it to the TOP of `~/Downloads/`. Numbering in `reports/registry.json`; the
write+number+copy logic is `src/report/build.py::finalize_report`.

## Current state (what works, LIVE)
- **16,470 CT legislators** (data.ct.gov `h2b3-nyih`), cannabis-era cutoff **2012**
  (`Pipeline._cannabis_era`); ~447 cross-referenced.
- **1,808 cannabis people**: business-registry ownership network (recursive LLC→LLC→
  people) + **eLicense roster scrape** (backers `ckbRoster75` + key employees
  `ckbRoster77`; `src/collectors/elicense_roster.py`).
- **Relationship resolution** (`src/resolve/relationship.py`): surname match = lead
  only; each is web-resolved (DuckDuckGo via `web_search.py`) → CONFIRMED / PROBABLE /
  POSSIBLE / SURNAME ONLY, with crime/legislative false-positive filters (`_NEG`) and a
  distinctive-entity-word cannabis-context check. Caches: `verified_resolutions.json`
  (VERSIONED — bump `RESOLVER_VERSION` on logic change), `findings_cache.json`,
  `spouses.json`, `voting.json`, `websearch/`, `elicense/`.
- **Findings (live):** CONFIRMED **Art Linares** (former senator = cannabis owner,
  Rodeo/Connecticut Social Equity LLC; opposed cannabis 2013-17 then operator 2025;
  spouse = Stamford Mayor Caroline Simmons); PROBABLE **Juan Candelaria** (exact-name
  credential); POSSIBLE **Geraldo Reyes ~ Patricia Reyes** (same town Waterbury).
- **Spouse second-hop** (different-surname): `find_spouse_names` + cross-ref vs cannabis
  set (safe — only asserts on a real match). **Voting timeline** per connected
  legislator (`src/resolve/voting.py`). **Municipal §3** = Glassman→Curaleaf (sourced,
  `data/known_municipal_findings.json`).

## Report structure (PDF, build.py `write_findings_pdf`)
Cover → **Executive Summary** → §1 State Senators (table) → §2 State Representatives
(table) → Legislative Voting & Timeline → §3 Municipal Leaders → Side note (recusals,
minor) → Zoning context → **Run Summary + Self-Validation** → Coverage Gaps → Coverage
→ Legal/Methodology → References. Headers CENTERED+UPPERCASE, attached to tables
(`_section`/`KeepTogether`); findings as wrapping tables (`_findings_table`, one row per
official). Only resolved findings shown; no surname-coincidence clutter.

## Key files
- `src/pipeline.py` — orchestration; `_legislator_cannabis_leads` (surname leads),
  resolution loop (verified-cache reuse + WEB_BUDGET), spouse + voting passes, counts.
- `src/resolve/{relationship,web_search,verified_cache,voting}.py`
- `src/collectors/{ownership_network,elicense_roster,live_socrata,...}.py`
- `src/municipal.py` + `src/analyze/municipal.py` (Simsbury four-class pattern)
- `src/report/build.py` (the PDF), `data/known_municipal_findings.json`
- Periodic state log: `CONTEXT_NOTE.md` (read its TOP section for latest).

## V2 backlog status — items 1-5 DONE (2026-06-12). See CONTEXT_NOTE.md top sections
## for the per-item detail. 64 tests pass. Don't stop at "no bulk API" — use live web/
## eCRIS/OSE/BoardDocs/news/company filings for direct verification.
1. [DONE] Relationship-tier RELABEL → VERIFIED / HIGH PROBABILITY / POSSIBLE / UNVERIFIED
   NAME MATCH. Display-layer map `report.build.DISPLAY_TIER`/`display_tier()` (internal
   logic strings unchanged). `tests/test_tiers.py`.
2. [DONE] **Campaign finance** (SEEC eCRIS) — `collectors/seec_finance.py` drives the
   eCRIS contribution search (ASP.NET); pipeline `_campaign_finance()` links cannabis
   donations to legislators; report "Campaign Finance" section. `tests/test_seec_finance.py`.
3. [DONE] **Lobbyist analysis** (CT OSE) — `collectors/ose_lobbyists.py` (Socrata
   `4ixq-tnwe`); pipeline `_lobbyist_analysis()`; report "Cannabis Lobbying" section. Also
   FIXED `is_cannabis_text` substring bug (thc-in-healthcare). `tests/test_ose_lobbyists.py`.
4. [DONE] **Municipal expansion** — `collectors/town_attorneys.py` +
   `data/town_attorney_chains.json` (sourced firm cannabis practices); municipal pipeline
   builds host-town roster + town-attorney chains (sourced + bounded web-discovery, no
   fabrication); report §3b/§3c. `tests/test_town_attorneys.py`.
5. [DONE] **CGA roll-call votes** — `resolve/cga_votes.py` parses cga.ct.gov roll-call
   PDFs (final passage per chamber) + `recusal_search()`; wired into the voting pass +
   report voting section. `tests/test_cga_votes.py`. (2012 medical bill URL TBD = gap.)

### STILL OPEN (V2 continued):
6. Family expansion (parent/child/sibling) + appearance-vs-actual conflict CATEGORY
   split + per-finding political-vs-cannabis side-by-side timeline.
7. Restructure the .md report to match the PDF (low priority; PDF is the deliverable).
8. CGA 2012 medical-marijuana roll-call (HB 5389 — different/older cga.ct.gov URL
   structure; 2021 adult-use both chambers already wired).
9. SEEC: per-receipt permalinks (currently cite the search page) + contract-lobbyist
   client registrations from the OSE eLobbyist portal (not in the bulk dataset).

## Gotchas
- Verified cache is VERSIONED: change resolver logic → bump `RESOLVER_VERSION` in
  `src/resolve/verified_cache.py` or stale verdicts get reused.
- Legislator dataset's latest year is 2023 → "after leaving" in timelines can be off for
  current members (data limitation).
- `urllib` has no CA bundle in this env → use `httpx`/`curl` (live_socrata uses httpx).
- macOS: no `timeout` cmd; reports render via PyMuPDF (`fitz`) for inspection.
- cga.ct.gov + seec.ct.gov use a state TLS chain this env doesn't bundle → cga_votes
  `_client()` uses httpx `verify=False`; seec_finance/town_attorneys catch SSL via the
  generic exception path. SEEC + OSE + CGA all LIVE-only (offline = fixture/inert).
- New live collectors run in the main Pipeline.run() (SEEC `_campaign_finance`, OSE
  `_lobbyist_analysis`, CGA inside the voting pass) and MunicipalPipeline.run()
  (town-attorney chains). A full live run is slower now (SEEC employer searches budget
  80 + CGA PDF fetches + recusal web searches); all bounded + cached.
