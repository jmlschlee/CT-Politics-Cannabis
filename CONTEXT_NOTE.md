# CONTEXT NOTE — CTCannabisPoliticalCheck (repo dir: ct-cannabis-conflicts)

Periodically-saved progress for this build. See HANDOFF.md for the resume brief.

## 1.1.1 — CRITICAL FALSE-ATTRIBUTION FIX + LIVE-FIRST (2026-06-12)
User: "vincent candelora is nowhere on green leaf holdings llc nor does he lobby for
cannabis... major hallucination... links lead to broken pages... ALWAYS run live."
ROOT CAUSE: the false positives were in the OFFLINE FIXTURES (synthetic demo data),
NOT the live pipeline. The original golden-test fixtures attached REAL CT legislators'
names (Vincent Candelora HD-86, Juan Candelaria HD-95) to fake cannabis records
(`business_registry.json` Green Leaf Holdings member; I had also added a fabricated
`ose_lobbyists.json` Candelora/Curaleaf entry). The offline demo report rendered these
as real findings → defamation-by-fixture.
FIXES (all shipped, release v1.1.1 id 338886288):
- Fictionalized report-facing real names → Gregory Hallowell / Marcus Vance (+ private
  donors/lobbyists Witkos→Brightwood, Burnes/Fell/Gibbs/Tirella→fictional). KEPT the
  protective never-merge guard for the REAL Candelaria/Candelora pair in matcher.py +
  config.yaml (that protects them in LIVE runs; it does NOT attribute cannabis).
- OFFLINE reports now show a loud red "SYNTHETIC FIXTURES" banner (mode!=LIVE) naming
  the fictional names + noting the Simsbury/Glassman municipal item is real-sourced.
- Broken links fixed: stripped fake `?id=`/`?type=` params from fixture URLs → real CT
  portal roots; findings identity-link now prefers web-evidence sources (that NAME the
  person) and only real http(s) URLs; honest "verify same person" label (only VERIFIED
  tier = certain).
- LIVE-FIRST: reduced politeness delays (per_host 2.0→0.8, web 0.8→0.4, SEEC 1.5→0.8)
  so a full LIVE run now completes in ~4 MIN (was 40+). Program already defaults to live.
- **VERIFIED LIVE report #32** (12pp, all sections combined, REAL data): §1 Senators =
  **Art Linares VERIFIED** (Connecticut Social Equity LLC / Rodeo) w/ real CT Examiner +
  CT Insider news links; 111 leads; SEEC + OSE + CGA roll-calls + 53-town municipal; NO
  synthetic banner (live); NO Candelora false positive. Copied to Downloads.
  Live Candelaria→"The Goods THC Co." is a REAL registry match flagged PROBABLE for
  human verification (correct behavior, not fabricated).
- KNOWN minor: voting-stance web search returns a few tangential citations (NPS/Wikipedia)
  — cosmetic noise in the voting section, not the identity links.
- VERSION→1.1.1. 64 tests pass.

## 1.1.0 — SINGLE FILE + REPORT FEATURES (2026-06-12)
Release https://github.com/jmlschlee/CT-Politics-Cannabis/releases/tag/v1.1.0 (id
338883752). User asks handled:
- **"why is the senator section empty of Linares suddenly"** — because the report in
  Downloads was the OFFLINE demo (#28); offline fixtures have only Aldenberry/Folger/
  Candelora (reps), NO senator cannabis ties. **Art Linares only appears in a LIVE run**
  (resolved from the live ownership network + web). Not a regression. Noted in release.
- **SINGLE FILE** (headline "this is one program!"): `build_single_file.py` bundles all
  41 `src/**` modules + 23 data files (config/sources yaml, data/*.json, tests/fixtures/
  *.json) base64-packed into **`CTCannabisPoliticalCheck_app.py`** (466KB). A meta-path
  `_EmbeddedLoader` serves `src.*`; data is materialized to `$CTCPC_HOME` (default
  ~/.ct_cannabis_check) and each module's `__file__` is set to HOME/<path>.py so
  `config.ROOT = Path(__file__).parent.parent` = HOME and every ROOT-relative read works
  unchanged. VERIFIED: runs from /tmp with no src/ access, full report. Regenerate after
  any src/ edit: `python3 build_single_file.py`.
- **YEARS OF SERVICE** in §1/§2 official cell ("Served: <years_served>").
- **IDENTITY SOURCE LINK** next to every name (`refs.link(srcs[0],'identity source ↗')`)
  + per-row "Verification (same-person sources)" line (or red "NO PRIMARY SOURCE").
- **DISCLAIMER** const `report.build.DISCLAIMER` (verify everything / no legal
  implications / lawful disclosed activity) — red box on cover + `st.error` in streamlit.
- **LOBBYING & MONEY**: lobbying section now joins cannabis-lobby orgs to SEEC rows by
  employer name → donations sub-table (giver→recipient, amount, date). Section renamed
  "Cannabis Lobbying & Money (CT OSE + SEEC)".
- VERSION→1.1.0; README "New in 1.1" + single-file note. 64 tests pass. Offline #30.
  Downloads synced incl. the single file.

## RELEASE 1.0 + FIXES + MUNICIPAL CATEGORY (2026-06-12)
After the 5 V2 items, user asked for: municipal Glassman pattern as a generalized
CATEGORY across all towns; periodic sync of the Downloads .py/CONTEXT/HANDOFF
copies; fix recurring table-wrap + unverified-line-item issues; and PUSH RELEASE 1.0
to GitHub (3 OS zips + streamlit app). Done:
- **TABLE-WRAP FIX**: the #1 tier relabel made labels longer ("HIGH PROBABILITY",
  "UNVERIFIED NAME MATCH") but the §1/§2 findings Tier column was still 56pt → bad
  wrapping. Widened to 80pt (cols now [92,116,80,PAGE_W-288]). All other new tables'
  colWidths already sum to PAGE_W exactly (no overflow).
- **VERIFICATION ON EVERY LINE ITEM**: `_findings_table` now appends a Verification
  line to EVERY row — clickable sources (from each tie's source_urls + resolution
  sources) OR an explicit red "NO PRIMARY SOURCE LOCATED — treat as UNVERIFIED".
- **MUNICIPAL CATEGORY GENERALIZED** (Glassman → all towns): `town_attorneys.py`
  gained `discover_official_tie(town)` — live, conservative web search that emits a
  POSSIBLE lead only when a town-leadership ROLE + cannabis term + relationship cue
  co-occur (never fabricated). MunicipalPipeline runs BOTH town-counsel discovery and
  official-tie discovery for every host town (budget max(60, towns+5)); new
  `official_tie_findings` + count `official_tie_leads`. Report §3 reframed (Glassman =
  worked example of a category, now generalized): new §3a "Municipal Official Cannabis
  Ties (Glassman Category, Generalized)" table + §3b town-attorney chains + §3c roster.
- **RELEASE 1.0**: added `VERSION="1.0.0"`/`app_version()` to report/build.py (exported);
  `streamlit_app.py` (light-theme web UI: offline-demo default + live option, runs the
  pipeline, shows metrics + resolved connections + PDF download); requirements.txt +=
  pymupdf, streamlit; README rewritten for v1.0 (New-in-1.0 section, live-source table,
  64 tests). Target GitHub repo = **jmlschlee/CT-Politics-Cannabis** (was empty:
  LICENSE+README only, default branch main, no releases). Repo had NO git/remote/
  streamlit/release infra before this (the CannaScope infra in MEMORY.md is a DIFFERENT
  project). ⚠️ A fine-grained GitHub PAT was provided in chat for the push — MUST be
  rotated/revoked now that the release is published.
- 64 tests pass. Offline report #28. NOTE: a full LIVE run takes 40+ min (sequential
  SEEC 80 + web resolution 40 + spouse 50 + per-legislator voting/CGA/recusal + town
  discovery) — bounded + cached; killed the validation run, caches persisted.

## V2 #5 — CGA ROLL-CALL VOTES + RECUSAL DONE (2026-06-12) — ALL 5 V2 ITEMS DONE
ACTUAL per-legislator floor votes on the landmark cannabis bills from cga.ct.gov
(no longer just web-sourced stance), plus a per-member recusal/ethics check.
- `src/resolve/cga_votes.py::CgaRollCalls`: for each bill in `CANNABIS_BILLS`
  (2021 SB/HB 1201 RERACA adult-use; 2012 HB 5389 medical), reads the bill-status
  page, collects its VOTE PDF links, parses each roll-call PDF, and keeps the
  FINAL-PASSAGE vote per chamber = HIGHEST sequence number (amendments precede the
  vote on the bill; concurrence is last). `legislator_vote(name)` → YEA/NAY/ABSENT
  matched by surname + first initial. Cached data/cache/cga/. LIVE-only (offline
  inert — returns [] BEFORE reading cache, for deterministic tests).
- PDF PARSE: two layouts unified in `_PAIR_RE` + `_surname_initial()` — Senate
  prints "letter district FIRST M. LAST"; House prints surname-only "letter LAST"
  or "letter LAST, F.". cga.ct.gov uses a TLS chain this env lacks → `_client()`
  sets httpx `verify=False` (read-only public records).
- `recusal_search(name)` → FOUND RECUSAL / NO RECUSAL FOUND / INSUFFICIENT DATA via
  web_search (recus|stepped aside|conflict + cannabis).
- Pipeline voting pass now attaches `rec["rollcall"]` + `rec["recusal"]` to each
  connected legislator's `d["voting"]` (cache key now requires "rollcall" present so
  old cache entries refresh). Report "Legislative Voting & Cannabis Timeline" stance
  cell now leads with the ACTUAL YEA(green)/NAY(red) floor votes + tally + cga cite,
  then the italic web stance, then a Recusal line.
- Tests `tests/test_cga_votes.py` (4). Suite 60→**64 pass**. VERIFIED LIVE: 2021
  SB/HB 1201 both chambers loaded (House 76-62 6/16; Senate concurrence 16-11 6/17 —
  the real RERACA votes); lookups correct (Candelora NAY, Candelaria YEA, Kelly NAY,
  Anwar ABSENT). 2012 HB 5389 returned 0 vote links (different/older URL structure)
  → honest coverage gap, graceful.
KNOWN: 2012 medical-era roll-call not yet wired (URL structure differs). A live
full run was kicked off to validate all 5 features end-to-end (see /tmp/live_run.log).

## V2 #4 — MUNICIPAL EXPANSION DONE (2026-06-12)
Expanded §3 beyond the single Simsbury case to ALL host towns + town-attorney
cannabis chains, WITHOUT fabricating town↔firm links (project hard rule).
- `data/town_attorney_chains.json`: SOURCED registry of CT municipal-law firms with
  a documented cannabis practice (Pullman & Comley [Andrew Glassman chair], Murtha
  Cullina, Robinson & Cole, Shipman & Goodwin, Halloran Sage, Updike Kelly) — each
  cited to the firm's own cannabis page; `towns_advised` only where sourced
  (Simsbury→Pullman & Comley). The Glassman/Curaleaf template generalized.
- `src/collectors/town_attorneys.py::TownAttorneyChains`: `sourced_findings()` emits
  the cited assignments; `discover_town_counsel()` is a LIVE, bounded web search that
  only returns a finding when a registry firm name AND a town-counsel context keyword
  (`_COUNSEL_CTX`: "town attorney/corporation counsel/retained/...") co-occur in the
  SAME result — never fabricated. `match_firm()` matches the firm head token;
  `_firm_key()` drops entity suffix + stray single letters.
- `MunicipalPipeline.run()` builds `host_town_roster` (every host town from dossiers
  + operators + zoning status, annotated with cannabis-practice counsel where found)
  and `town_attorney_findings` (sourced + ≤25 web-discovered host towns). New counts
  `host_town_roster`/`town_attorney_chains`; coverage entry (notes town-counsel
  rosters aren't bulk-published → unlisted towns INCOMPLETE).
- Report §3 expanded: §3b "Town-Attorney Cannabis Chains" (sourced=red asserted vs
  web-discovered=amber "LEAD — VERIFY") + §3c "Host-Town Roster" (all towns, operator,
  zoning [restrictive=red], counsel or "not identified"). intro3 reworded.
  `write_findings_pdf` already receives `municipal`.
- Tests `tests/test_town_attorneys.py` (5). Suite 55→**60 pass**. VERIFIED LIVE:
  discovery found Manchester+Montville → Shipman & Goodwin (counsel-context gated),
  Stamford → honest None. Offline report #25 renders §3b (Simsbury→Pullman & Comley
  →Andrew Glassman, sourced) + §3c roster.
NEXT (in progress, LAST item): #5 Per-bill CGA roll-call tallies (cga.ct.gov vote
pages) + recusal/ethics search per connected legislator.

## V2 #3 — LOBBYIST ANALYSIS (CT OSE) DONE (2026-06-12)
Cannabis-industry lobbyist roster + legislator overlap, LIVE from CT Office of
State Ethics (data.ct.gov Socrata `4ixq-tnwe`, "Lobbyist Communicators 2025-2026",
782 rows: last/first name, organization_name=who they lobby for, city, register
date, member type).
- `src/collectors/ose_lobbyists.py::OseLobbyistCollector` (live Socrata via
  `live_socrata.socrata_get`; offline fixture `tests/fixtures/ose_lobbyists.json`).
  Flags cannabis lobbying when organization_name matches `is_cannabis_text` OR a
  curated `CANNABIS_OPERATOR_MARKERS` list (operators whose name omits "cannabis":
  curaleaf/acreage/fine fettle/theraplant/verano/budr/...) OR registry-supplied
  extra markers. Reuses the `Lobbyist` model (organization → client_name).
- **BUG FOUND + FIXED (shared correctness win): `is_cannabis_text` used plain
  substring `in` → "thc" matched "heal-THC-are" → Hartford HealthCare / Molina
  Healthcare / Day Kimball all false-flagged as cannabis.** Rewrote
  `analyze/cannabis_terms.py` to a WORD-BOUNDARY regex (`\b(?:marker...)`, stem
  still allowed so "cultivat" catches "cultivation"). Live OSE cannabis count
  17→4 (false healthcare hits gone; real = CT Cannabis Chamber x2, Budr x2). All
  55 tests pass after — no other behavior broke.
- Pipeline `_lobbyist_analysis()` (both modes): builds the cannabis-lobbyist roster
  grouped by org + surname-cross-refs each communicator to a cannabis-era legislator
  → `legislator_matches` tiered (same_person="LEGISLATOR IS A CANNABIS LOBBYIST" /
  same_first / surname-only). Stored on `result.lobbying`; counts
  `cannabis_lobbyists` + `cannabis_lobbyist_leg_matches`; coverage entry (notes the
  contract-firm client registrations are OSE-portal-only, not in this bulk dataset).
- Report: new section "Cannabis Lobbying (CT Office of State Ethics)" (after
  campaign finance, before §3) — legislator-overlap table (red) + cannabis-lobby-org
  roster table; `write_findings_pdf` gained `lobbying=` param. Run Summary metrics.
- Tests `tests/test_ose_lobbyists.py` (4). Suite 51→**55 pass**. VERIFIED LIVE
  (4 cannabis lobbyists) + offline (Candelora flagged as himself a cannabis lobbyist).
NEXT (in progress): #4 Municipal expansion — all 53 host towns × official types +
town-attorney→cannabis-client chains (currently Simsbury/Glassman→Curaleaf only).

## V2 #2 — CAMPAIGN FINANCE (SEEC eCRIS) DONE (2026-06-12)
Cannabis money into CT legislators, pulled LIVE from the SEEC eCRIS portal (no
Socrata bulk API exists — used the public contribution search per the V2 mandate).
- SOLVED the ASP.NET contribution search `SearchingContribution.aspx`: GET grabs
  __VIEWSTATE/__VIEWSTATEGENERATOR, POST `txtEmployerName`/`txtContributorName`
  (+ `txtTransactionStartDate`=01/01/2012) + `btnSearch` → parse the
  `gvSearchResult` grid. Cells carry inter-character markup → strip tags to EMPTY
  (not space) or names come out "E s t h e r". Strip trailing "(SEEC##)" form code.
- `src/collectors/seec_finance.py`: `SeecContributionSearch` (driver, per-query
  cache under data/cache/seec/, live-only) + `SeecCampaignFinance` (collect by
  EMPLOYER for each cannabis business + by CONTRIBUTOR for principals/legislators;
  dedup by receipt id; employer/contributor budgets 80/40, logs caps — no silent
  truncation) + `is_legislative()`/`normalize_entity()`/`parse_grid()`. SEPARATE
  from the legacy fixture-only `campaign_finance.CampaignFinanceCollector` (left
  intact — base pipeline + test_integration depend on it).
- `models.py`: new `CampaignContribution` (receipt_id, contributor, employer,
  occupation, city, amount, date, recipient_committee, office_sought, district,
  committee_type, party, election_year, matched_by + Provenance).
- Pipeline `_campaign_finance()` (runs BOTH modes; offline uses fixture
  `tests/fixtures/campaign_contributions.json`): gathers biz names + person names,
  collects, keeps only STATE LEGISLATIVE recipients, links each to a cannabis-era
  legislator by tokenizing the committee name vs the canonical-surname index
  (+district disambig — `surname_key` needs a full name so compare `canonical(tok)`
  directly). Groups by recipient w/ totals. Stored on `result.campaign_finance`;
  counts `cannabis_contributions`/`cannabis_contribution_total`; coverage entry.
- Report: new section "Campaign Finance — Cannabis-Linked Contributions (SEEC
  eCRIS)" (after Voting timeline, before §3) — per-recipient table (legislator/
  committee · donors+employers+years · amount · eCRIS source); "lawful disclosed
  donation, not an allegation" framing; cap caveat; Run Summary metric rows.
  `write_findings_pdf` gained `campaign_finance=` param (threaded via write_all).
- Tests `tests/test_seec_finance.py` (6). Suite 45→**51 pass**. VERIFIED LIVE:
  Curaleaf → 13 contributions, 5 to legislative committees (Witkos 2016/18/20 SD-8,
  "Marc for Rep" d149, "Kim Becker for CT" d62). Offline report #23 renders the
  section ($400 across 3, Aldenberry+Folger linked, Witkos unmatched=not in roster).
NOTE: Witkos (Curaleaf employees donated to him) is ALSO the Simsbury SD-8
legislative-overlay official — strengthens that municipal thread.
NEXT (in progress): #3 Lobbyist analysis (CT Office of State Ethics) — cannabis
lobbyists/firms/chambers tied to legislators.

## V2 #1 — TIER RELABEL DONE (2026-06-12, report #22)
User directive: work the V2 backlog in order 1→2→3→4→5. #1 complete.
Relationship/lead tiers now render with reader-facing labels while the INTERNAL
logic strings stay stable (so the verified-resolution cache, the matcher, and the
suite are untouched):
  CONFIRMED → VERIFIED · PROBABLE → HIGH PROBABILITY · POSSIBLE → POSSIBLE ·
  SURNAME ONLY / NOT VERIFIED → UNVERIFIED NAME MATCH.
- New `report.build.DISPLAY_TIER` + `display_tier()` (module-level, exported);
  `_dtier = display_tier` used at every reader-facing tier render: Executive
  Summary line + new **Confidence tiers legend**, §1/§2 findings-table cell,
  §3 municipal known-findings cell, Run Summary metric labels, self-validation
  warnings. `Confirmed:` lead-in → `Verified:`.
- SCOPED DELIBERATELY: the municipal four-class taxonomy (CONFIRMED / UNCONFIRMED
  / UNSUPPORTED / CONTEXT in `analyze/municipal.py`) and the matcher identity
  confidence are SEPARATE systems with different meanings — NOT relabeled (mapping
  UNCONFIRMED→"UNVERIFIED NAME MATCH" would be semantically wrong). Only the
  municipal *known_findings* `tier` field (a relationship tier; Glassman=CONFIRMED)
  maps → VERIFIED.
- New `tests/test_tiers.py` (4 tests). Suite 41→**45 pass**. Verified in rendered
  PDF #22 (PyMuPDF): exec "0 VERIFIED, 3 HIGH PROBABILITY, 0 POSSIBLE", legend +
  run-summary relabeled, old "CONFIRMED legislator" phrasing gone.
NEXT (in progress): #2 Campaign finance (SEEC eCRIS) — cannabis operator/exec/
attorney/lobbyist/PAC donations → legislators; new report section + totals.

## V2 OVERHAUL — PART 1 (2026-06-12, report #20)
User V2 spec = huge. Done this turn (the critical + explicit items):
- **CONTRADICTORY STATS FIXED** (was: Linares CONFIRMED but Run Summary "Confirmed: 0"
  because summary used the base `published` Finding count, not the leads). Pipeline
  now emits confirmed/probable/possible/senator/representative/vote_review counts FROM
  legislator_cannabis_leads. Report Run Summary uses them + a **Self-Validation** line
  that warns if summary != rendered (now: "Self-validation PASSED").
- **PRESENTATION**: section headers now CENTERED + UPPERCASE (`_H2`/`_H3`, TA_CENTER);
  header kept attached to its table via `KeepTogether` (`_section()` — fixes detached
  headers); **EXECUTIVE SUMMARY** added at top (leads with findings + confirmed names);
  the big "required sources" table MOVED to the back as "Coverage Gaps" (caveats/
  methodology now at back, findings first).
- **CGA VOTES (finished, part 1)**: `src/resolve/voting.py::cannabis_voting_record`
  web-sources each connected legislator's cannabis STANCE + builds a political-vs-
  cannabis TIMELINE (before/during/after service). New report section "Legislative
  Voting & Cannabis Timeline". Cached `data/cache/voting.json`. LIVE: **Art Linares =
  OPPOSED cannabis 2013-17, cannabis involvement registered 2025 (after leaving)** —
  the exact pattern requested. (Precise per-bill roll-call tallies from cga.ct.gov vote
  pages still a further integration.)
- Report #20, 6 pages, 41 tests. Pushed to Downloads.

### STILL TODO (V2 backlog — large integrations, prioritized):
1. Relationship CONFIDENCE relabel to VERIFIED / HIGH PROBABILITY / POSSIBLE /
   UNVERIFIED NAME MATCH (currently CONFIRMED/PROBABLE/POSSIBLE).
2. Campaign finance (SEEC eCRIS) — donations from cannabis operators/execs/attorneys/
   lobbyists/PACs to legislators; new section + totals.
3. Lobbyist analysis (OSE) — cannabis lobbyists/firms/chambers tied to legislators.
4. Municipal EXPANSION beyond Simsbury: all 53 host towns, every official type
   (mayors/selectmen/managers/EconDev/P&Z chairs/town attorneys/corp counsel) + TOWN
   ATTORNEY chains (Pullman&Comley, Robinson&Cole, Updike Kelly, Shipman, Halloran Sage,
   Murtha Cullina -> cannabis clients -> which towns they advise).
5. Per-bill CGA roll-call tallies (cga.ct.gov vote pages) + recusal search per legislator.
6. Family expansion (parent/child/sibling, not just spouse) + appearance-vs-actual
   category split. Timeline section per finding (political vs cannabis side-by-side).

## TABLE-WRAP FIXES + FALSE-POSITIVE CLEANUP (2026-06-12, report #19)
Fixed the ugly table wrapping (build.py):
- Headers double-escaped (`&amp;` showed literally) -> use plain "and" in headers
  (`_wrap_table` already `_esc()`s them).
- "CONFIRMED" broke mid-word in the narrow Tier column -> switched `cell` style from
  `wordWrap="CJK"` to default word-wrap (splitLongWords=1; keeps whole words, only
  splits a token if it truly cannot fit) + widened Tier col 48->56.
- 4 near-identical Linares rows -> `_findings_table` now groups ONE ROW PER OFFICIAL,
  merges that official's cannabis ties, de-dups evidence, trims long text (_trim).
  Same for the municipal table.
FALSE POSITIVES removed (resolver tightened, `relationship.py`):
- `_NEG` now uses STEMS (indict, charge, traffick, +crimin/porn/abuse/assault/fraud)
  so "indicted/charged/trafficker" all match -> a different "Sean Williams" (criminal
  case) no longer creates a finding.
- cannabis-context check no longer uses a SHORT entity token: "CT BGP LLC" -> "ct"
  matched "Connecticut/district" everywhere -> Figueroa's own ELECTION article counted
  as cannabis. Now only DISTINCTIVE entity words (>=5 chars, non-generic) + cannabis terms.
- Verified cache now VERSIONED (`RESOLVER_VERSION=3` in verified_cache.py): bump it when
  resolver logic changes -> stale verdicts auto-invalidate (load returns {} on mismatch).
Clean result: CONFIRMED Art Linares (family venture, consolidated 1 row), PROBABLE Juan
Candelaria (exact-name credential), POSSIBLE Geraldo Reyes~Patricia Reyes (same town
Waterbury). Sean Williams + Figueroa false positives GONE. §3 Glassman->Curaleaf intact.
Report #19, 5 pages. 41 tests. Entry file clean.

## TABLES + SPOUSE SECOND-HOP (2026-06-12, report #15)
- FINDINGS NOW RENDER AS WRAPPING TABLES (user: the text-list "looks horrible").
  `_finding_row`/`_findings_table` in build.py -> §1 Senators / §2 Reps / §3 Municipal
  each a `_wrap_table` [Official&office | Cannabis tie (person/business/license) |
  Confidence | Assessment&evidence(+sources)]. Full-width, aligned, green header.
- SPOUSE SECOND-HOP DONE (#3): `relationship.find_spouse_names` web-extracts a
  legislator's spouse; pipeline cross-refs the spouse NAME vs the cannabis credential
  set. SAFE BY DESIGN: only asserts when the extracted name MATCHES a cannabis person
  (garbage names like "Matthew Koma" never match -> no false positives), and only when
  the surname DIFFERS (the different-surname-spouse vector). Budget 50/run, cached in
  `data/cache/spouses.json` (grows across runs). This run: 21 spouses extracted, 0
  matched a cannabis credential (honest negative). Coverage entry added. Extraction is
  noisy ("Stamford Caroline" for Linares->Caroline Simmons) but the cross-ref filter
  contains it; SFI spouse-employer (portal-only) would make this precise.
- 41 tests. Report #15, 6 pages. Entry file CTCannabisPoliticalCheck.py clean.
STILL TODO: #2 CGA cannabis votes; improve spouse extraction (or wire SFI); restructure
the .md to match the PDF (PDF is the deliverable).

## REPORT RESTRUCTURE (2026-06-12, report #14) — Senators / Reps / Municipal
Per user: PDF reorganized into **§1 State Senators (past+present) + relatives**,
**§2 State Representatives (past+present) + relatives**, **§3 Municipal leaders +
connections**. Findings split by chamber (lead role "State Senator"/"State
Representative"). ONLY resolved connections (CONFIRMED/PROBABLE/POSSIBLE) shown —
all surname-coincidence / NOT-VERIFIED / "no relationship found" tables REMOVED
(user: "if no relationship found zero reason to include"). Recusals DEMOTED to a
one-line side note (user: most officials don't recuse when they should, so it's a
weak signal). Removed legacy PDF blocks (per-Finding confirmed/unverified, per-town
dossiers, ownership-network table, facility list). Zoning kept as a small context
subsection w/ moratorium reconciliation. 14 pages -> 6.
§3 MUNICIPAL uses the **Glassman -> Curaleaf** case (web-verified, sourced): Mary
Glassman (Simsbury First Selectman 2007-2014, backed Curaleaf siting) whose husband
Andrew Glassman chairs Pullman & Comley's cannabis practice (2022 Cannabis Chamber
Attorney of the Year) = CONFIRMED appearance concern (not substantial: she didn't
control the zoning vote). Seeded in `data/known_municipal_findings.json`, loaded by
MunicipalPipeline -> result.known_findings -> report §3. Live §1: Linares family
CONFIRMED; §2: Candelaria PROBABLE + Reyes/Williams/Figueroa POSSIBLE. 41 tests.
NOTE: write_findings_md (markdown) NOT yet restructured to match (PDF is the
deliverable); md still has old leads/coincidence sections — low priority cleanup.

## VERIFIED-RESOLUTION CACHE (2026-06-12, report #12) — "faster once confirmed"
User: once a credential/relationship is verified, cache+compact it so re-analysis is
faster. DONE: `src/resolve/verified_cache.py` — `data/cache/verified_resolutions.json`
keyed by canonical (official::cannabis_person::business) -> {tier, evidence, sources,
searches, as_of}, written COMPACT (empty fields dropped, no whitespace). Pipeline
resolution loop now: rank leads (town-match, name-sim) -> for each, REUSE the cached
verdict for FREE if present (no web), else resolve fresh within WEB_BUDGET=40 and store.
So cached verdicts cost nothing and the freed budget resolves NEW leads -> verified
COVERAGE GROWS across runs (run A cached 40, B 80, C 110) until all 111 leads cached,
after which the web-resolution step is instant. `--refresh-cache` forces re-verify.
Confirmed Linares FAMILY venture now fully matched (Arthur, Luis Arturo, Luis, Pedro
Linares all CONFIRMED to Connecticut Social Equity LLC / Rodeo). Plus the compact
human-facing `data/cache/findings_cache.json` (CONFIRMED/PROBABLE/POSSIBLE only).
NOTE: the remaining per-run time is DATA COLLECTION (16k legislator fetch + live
registry ownership network re-query) — caching that network result is the next perf
win (separate from the verified-resolution cache, which is done). 41 tests pass.

## eLICENSE SCRAPE + EXPANDED FINDINGS (2026-06-12, report #9)
- **eLICENSE ROSTER SCRAPE DONE** (`src/collectors/elicense_roster.py`): the ASP.NET
  GenerateRoster.aspx flow is solved — GET (grab __VIEWSTATE) → POST ckbRoster75
  (Backers) / ckbRoster77 (Key Employees) + btnRosterContinue → read Selected~Roster
  idnt → GET FileDownload.aspx?Idnt=..&Type=CSV (TAB-delimited). Yields **1,707
  individuals** (540 backers + 1,167 key employees) w/ name, CITY (town-match!),
  license #, the cannabis business, and real EFFECTIVE date. ckbRoster76 (rank-and-
  file employees) excluded per scope. Cached under data/cache/elicense/. LIVE-ONLY
  (offline excluded so tests stay deterministic). Roster checkbox map documented in
  the collector (73=Cultivator,75=Backer,77=KeyEmp,79=Micro,83=Retailer,85-90=medical).
- Cannabis-person universe 101 → **1,808**; surname leads 5 → **111**. Resolution
  PRIORITIZED (rank by town-match then name-sim; web-resolve top 40; rest = NOT
  VERIFIED, listed by name, honestly not cleared).
- **MORE REAL FINDINGS**: CONFIRMED Art Linares (now incl. ARTHUR LINARES directly =
  Connecticut Social Equity LLC + Rodeo); PROBABLE Juan Candelaria (exact-name
  credential match to The Goods THC Co.); POSSIBLE Geraldo Reyes~Patricia Reyes (both
  Waterbury, same town), Sean Williams, Anabel Figueroa.
- RESOLVER TIGHTENED (was false-positiving): added `_NEG` exclusions (traffick/
  sentenc/prison/committee/bill/vote/forum/legislat...) + strong-ownership-only `_OWN`
  + require cannabis-business context. Demoted false positives (David Wilson matched a
  different David Wilson [convicted trafficker] + a non-cannabis forum → now SURNAME
  ONLY; Gonzalez/Smith/Fazio common-surname → demoted). Added exact-name-credential
  baseline: a cannabis credential holder name-matching the official floors at PROBABLE.
- MORATORIUM RECONCILIATION (user flag): §3 zoning now cross-refs host towns — flags
  any Moratorium/Prohibited town that STILL hosts an operating business (pre-existing/
  grandfathered, e.g. a Curaleaf producer) since zoning governs NEW licenses only.
- DATE FIX: per-record registration date (no more identical create_dt for every agent).
- **COMPACT FINDINGS CACHE**: `data/cache/findings_cache.json` = the resolved
  CONFIRMED/PROBABLE/POSSIBLE findings w/ evidence+sources+date, for quick reference.
- 41 tests pass. Report #9 = 14 pages, 205 links.

STILL TODO (user's order was eLicense→#2→#3; eLicense + data fixes done this turn):
- #2 CGA cannabis roll-call votes for connected officials (fills §2 voting).
- #3 spouse second-hop (resolver searches "{leg} spouse"; auto-cross-ref spouse name
  vs cannabis records — different-surname path).

## RELATIONSHIP-RESOLUTION RE-ARCHITECTURE (2026-06-12, report #7) — THE BIG ONE
User mandate: surname matching is lead-GENERATION only, NOT a finding. The system
must ACTIVELY resolve each lead from public sources before assigning confidence.
DONE — this is now a real investigation:
- `src/resolve/web_search.py` — reproducible DuckDuckGo HTML search from the PROGRAM
  (cached under data/cache/websearch). The program does its own web research.
- `src/resolve/relationship.py::resolve_relationship` — for each surname lead, runs
  5 targeted web searches (news/bios/company/press + "{leg} spouse") + (optional)
  registry co-ownership, extracts EVIDENCE, classifies into 4 tiers:
  CONFIRMED (primary source directly establishes) / PROBABLE (multiple independent) /
  POSSIBLE (some evidence) / SURNAME ONLY (searched, no relationship found). Records
  exactly which searches ran + why verification succeeded/failed.
- Wired into pipeline (live only; offline keeps surname confidence). Leads re-sorted
  CONFIRMED-first.
- LIVE RESULT: **Art Linares → CONFIRMED** (former state senator 2013-18 who voted on
  cannabis is HIMSELF a cannabis owner — Rodeo/Linares Faye LLC; news-sourced; his
  spouse = Stamford Mayor Caroline Simmons, a different-surname official). The other 4
  (Thomas/Urban/Abrams/Foster) → SURNAME ONLY (searched, no evidence = coincidences).
  Mary Daugherty Abrams false-positive fixed (her obituary's family words; tightened
  rel-evidence to require cannabis context / the principal's name).

PDF NOW FINDINGS-FOCUSED (report #7, 9 pages, 189 links):
- §1 "Resolved cannabis connections (findings)" — CONFIRMED/PROBABLE/POSSIBLE with
  evidence snippets + clickable sources + "Searches performed"; §1b "Surname leads
  checked — no relationship found" (transparency table).
- REMOVED from PDF: the ownership-network/registered-agent table (kept in code for
  matching, per user) + the passive facility-map appendix (no connections = not a
  finding). §2 voting, §3 zoning, completeness verdict retained.
- DATE BUG FIXED: per-record registration date (no more identical create_dt data-load
  date for every agent); leads show the cannabis business's real reg date.

STILL TODO (user's stated next: "elicesnce roster scrape then cga cannabis votes"):
- eLicense GenerateRoster.aspx scrape (backers/key-employees, ASP.NET __VIEWSTATE).
- CGA cannabis roll-call votes + recusals for connected officials (fills §2).
- Systematic spouse second-hop (resolver searches "{leg} spouse" but doesn't yet
  auto-check if the spouse is cannabis-connected — surfaced Caroline Simmons for
  Linares but not yet cross-referenced).

## ACCURACY + DATING + ZONING PASS (2026-06-12, report #6)
User directives applied: (a) KEEP public addresses/dates (don't drop — they're
public record AND a real identity signal), (b) integrate DCP license categories +
backers/key-employees, (c) stamp EVERY record with date/town/location/LLC/license
type/live URL, double-checked live.

DONE:
- `ownership_network.py` now RETAINS residence_city/residence_address/business_city +
  the cannabis business's registration_date (from Business Master date_registration,
  not the data-load create_dt) + license_type/number + retrieved_date. `CannabisPerson`
  model gained those fields.
- TOWN-AWARE LEAD ACCURACY (`Pipeline._legislator_cannabis_leads`): compares the
  cannabis principal's public RESIDENCE TOWN to the legislator's hometown. Same town =>
  elevate (PROBABLE/elevated); different known town => downgrade + note "likely NOT the
  same person"; this is the live double-check. Live: all 5 leads correctly stay
  POSSIBLE/REVIEW (Linares res Essex vs Westbrook; Urban res Stratford vs N.Stonington;
  Thomas res West Haven vs Norwalk; Abrams res Rocky Hill vs Meriden; Foster res
  Middletown vs Ellington) — none falsely elevated. Each lead now dated (reg date) +
  residence + license type + live-checked date + source links.
- MUNICIPAL ZONING LAYER: new dataset `khc7-gd9u` (CannabisZoningCollector) = all 169
  CT towns' cannabis status (Approved 56 / Moratorium 28 / Prohibited 29 / null 56).
  New report Section 4 "Municipal cannabis zoning, moratorium & approval actions".
- Report Section 1 leads table expanded to 5 wrapping cols incl residence/license/dates;
  every record carries reg date + live-checked date + clickable source.
- eLicense backer/key-employee roster (elicense.ct.gov GenerateRoster.aspx) is ASP.NET
  (__VIEWSTATE form, 15 ckbRoster checkboxes), NOT a bulk API → flagged in ALWAYS_GAP
  with the URL; the ownership-network principals/agents are the integrated substitute.
  Cannabis Applications `bqby-dyzr` (license#, type, applicant, live doc URL) +
  lottery applicants `y64a-qj22` exist for future integration.
- Report #6: 18 pages, ~294 clickable links. 41 tests pass.

## INVESTIGATION UPGRADE (2026-06-12) — real influence mapping, not a facility list
The big breakthrough: the CT Business Registry IS on data.ct.gov as bulk datasets:
Business Master `n7gp-d28j`, **Principals `ka36-64k6`**, **Agents `qh2m-n44y`** (+
Cannabusiness loan `8j58-xb79` w/ legislative_district). New module
`src/collectors/ownership_network.py::resolve_cannabis_network` walks cannabis
LLC -> principals/agents -> RECURSIVELY through LLC-owned-by-LLC chains (depth 3,
batched IN-list queries, ~10s) down to real PEOPLE. PRIVACY: residence/home
addresses dropped (the datasets include them; we never store them). Live: 95
cannabis businesses -> 64 matched -> 101 individuals; 32 unmatched (flagged
INCOMPLETE). Wired into pipeline as the live cannabis_persons source.

NEW screen `Pipeline._legislator_cannabis_leads`: cannabis principal/agent who
SHARES A SURNAME with a 2012+ legislator => POSSIBLE/REVIEW lead (self/relative/
coincidence — verify). Live surfaces **5 real leads**: Art Linares~Luis Arturo
Linares (Rodeo Rocky Hill LLC), Stephanie Thomas~Alex Thomas (C3 EJV II), Diana
Urban~Cody Urban (Cannabis Connection), Mary Daugherty Abrams~Keanaha Abrams
(Nutmeg Southwest JV), Jaime Foster~Crystal Foster (Budr Holding 2). All
POSSIBLE/REVIEW (different first names). Stored on result.legislator_cannabis_leads.

REPORT RESTRUCTURED into investigative sections (PDF + MD): COMPLETENESS VERDICT
(INCOMPLETE banner + table of exactly which required sources weren't queried) ->
§1 State legislators & cannabis connections (leads, wrapping table) -> §2 Cannabis
LLC ownership/principal/agent network (resolved people) -> §3 cannabis voting &
recusal analysis per connected official (era 2012 medical / 2021 adult-use, marked
INCOMPLETE — CGA roll-calls not bulk-integrated) -> run summary -> coverage ->
findings -> Appendix A facility map (DEMOTED, was the "filler"). Tables now WRAP
(Paragraph cells, wordWrap=CJK, full 504pt width) via `_wrap_table`.
`_completeness_verdict` + `REQUIRED_SOURCES`/`ALWAYS_GAP` drive the INCOMPLETE
logic: zero matches is labeled INCOMPLETE unless every required source queried.
Report #4 = 14 pages, 118 clickable links. 41 tests pass.

STILL INCOMPLETE (honestly flagged in-report, no bulk API): campaign finance
(SEEC), lobbyists (OSE), SFI (OSE), municipal officials/minutes/town-counsel,
CGA roll-call votes + recusals, local cannabis votes/moratoria/host agreements.
These are the next integrations (portal scraping, off by default per §6).

## LATEST (2026-06-12) — branding + numbered reports + 2012 cutoff
- **Program name = `CTCannabisPoliticalCheck`.** Single entry file at repo root:
  `CTCannabisPoliticalCheck.py` (live by default; `--offline`, `--no-municipal`,
  `--no-downloads`, `--since-year`). `make run` = live; `make run-offline` = demo.
- **Numbered, never-overwritten PDFs:** `reports/CTCannabisPoliticalCheck_<N>.pdf`
  starting at #1; `reports/registry.json` tracks `next` + history. `next_report_number()`
  = max(registry, highest on-disk file)+1 (robust to a lost registry). Each report is
  COPIED to the top of `~/Downloads/CTCannabisPoliticalCheck_<N>.pdf` (newest = top).
  Logic in `src/report/build.py::finalize_report` (called by the launcher AND
  `src/cli.py run`). `make clean` never touches reports/.
- **CT cannabis era cutoff fixed to 2012** (MEDICAL; ADULT-USE 2021), not 2010/1915.
  The 1915 was only the `h2b3-nyih` dataset's range; full roster is collected/stored
  but cross-referencing is scoped to members serving 2012+ via `_cannabis_era` /
  `--since-year` (config `default_since_year: 2012`). Live: 16,470 roster → **447**
  cross-referenced.
- **TRIPLE-CHECKED report #2:** 9 pages, title "CT Cannabis Political Check — Report #2",
  author CTCannabisPoliticalCheck, 9 clickable links (3 distinct data.ct.gov URLs),
  Downloads copy sha256 == reports copy, registry next=3. 41 tests pass.
- PDF cover rebranded; footer = "CT Cannabis Political Check". Status labels plain
  text in PDF (reportlab has no emoji), ✅/⛔ kept in MD.

---
## EARLIER PROGRESS (still valid)

## Base system (DONE, 31 tests pass)
State-legislator cannabis conflict screening. collect→store(DuckDB)→resolve
(rapidfuzz entity resolution + confidence tiers + common-surname/never-merge
guards)→classify(CGS §1-84/§1-85, §21a-421dd)→report(xlsx/md/pdf/review CSV).
Offline-first against `tests/fixtures/`. Entry: `python -m src.cli run --offline`.

## Municipal extension (IN PROGRESS)
Adds a town layer. Canonical pattern = Simsbury/Curaleaf worked example, which
exercises ALL FOUR output classes the classifier must produce:
  * CONFIRMED      — marriage (Glassman) + spouse's cannabis practice (Pullman&Comley)
  * UNCONFIRMED    — spouse's firm repping the HOST operator (Curaleaf) — NOT sourced
                     (firm's documented 2014 client was Advanced Grow Labs, different co.)
  * UNSUPPORTED    — local vendor (Flamig Farm) handling operator waste — checked,
                     no support; national TerraCycle packaging program ≠ local link
  * CONTEXT-ONLY   — legislator over the town (Witkos, SD-8, General Law) — no stake

### Connection taxonomy (6 types, each its own evidence bar) — §6
1 siting_zoning · 2 official_family_rep · 3 official_own_role ·
4 vendor_contractor · 5 donation · 6 legislative_overlay

### Hard rules
* PRIMARY-SOURCE GATE: family/representation links promote above REVIEW only on a
  primary source (campaign bio naming spouse, SFI spouse-employer, firm page naming
  client, deed/lease). Shared surname/town/broker tag = lead, never finding.
* Don't manufacture connective tissue: undocumented operator-specific link → say so.
* Appearance ≠ accusation: limited-formal-power check (who actually decided the
  vote?). Welcoming/championing ≠ control.
* Negatives are first-class findings ("checked, no support").
* Privacy: no home address/phone/DOB for officials OR relatives.

### Build order / status — COMPLETE (41 tests pass: 31 base + 10 municipal)
[x] models: CannabisFacility, MunicipalOfficial, FamilyLink, LawFirm, LocalEntity,
    VendorHypothesis, LegislativeOverlay, TownConnection (src/models.py)
[x] sources.yaml municipal block (sources 7-13)
[x] collectors/municipal.py (privacy gate on officials/family)
[x] analyze/municipal.py — taxonomy + four-class classifier + substantial_conflict
    (limited-formal-power via _decided_the_siting) + primary-source gate +
    parse_minutes (votes/recusals, respects explicit empty recusals, skips negations)
    + MUNICIPAL_POLICY statement
[x] municipal.py pipeline (host-town targeting from facilities + dossiers)
[x] report: "Town map" sheet + per-town dossier (four-class §4.1) + municipal_review_queue.csv
[x] fixtures (§5): cannabis_facilities, municipal_officials, family_links, law_firms,
    vendor_hypotheses, legislative_overlay, local_entities, meeting_minutes
[x] tests/test_municipal.py (10) + README municipal section + CLI (`run` auto-runs
    municipal; `--no-municipal` to skip)

### LIVE ONLINE RUN — WIRED + VERIFIED (2026-06-12)
`python -m src.cli run` (no --offline) hits real data.ct.gov Socrata bulk APIs.
WIRED LIVE: legislators `h2b3-nyih` (16,472; 230 current/16,242 former, is_former
computed from years_served vs dataset's latest year), cannabis establishments
`vw4a-3bnz` + retail `42yd-3x3d` (189 businesses → 53 host-town facility map).
PORTAL-ONLY (no bulk API → live_available=False, skip-with-flag, NOT scraped):
campaign finance (SEEC eCRIS), lobbyists (OSE), business principals/CONCORD (SOTS
UI), SFI (OSE), all per-town municipal sources. Honest result: 0 individual
findings (the confirming sources aren't bulk-available), 490 cannabis-era members
cross-referenced (CONCORD surname-in-business screen, scoped via _cannabis_era /
--since-year=2010 so 1915 legislators excluded), 189 facility dossiers (all
CONTEXT). PDF = 9 pages, 9 clickable data.ct.gov links, coverage table flags every
gap. Helpers: `src/collectors/live_socrata.py` (paged Socrata GET);
`fetch_live()` on legislators_current/dcp_cannabis/cannabis_facilities.
TWO CACHE BUGS FIXED: (1) collectors sharing source_name collided on cache →
cache key now includes class name; (2) offline now prefers FIXTURE over cache
(deterministic tests, ignores leftover live cache). 41 tests still pass.
Report: PDF/MD got a "Sources queried (coverage)" table + "Live datasets queried"
clickable links + compact host-town facility-map table (full four-class dossiers
only for towns with a non-CONTEXT connection). PDF status labels use plain text
(reportlab base fonts have no emoji glyphs; MD keeps ✅/⛔).

### Verified Simsbury output (offline)
1 host town; connections: 1 CONFIRMED (Glassman family-rep appearance, substantial=False),
2 UNCONFIRMED (Pullman&Comley→Curaleaf inference NOT asserted; Sanchez surname-only
review), 1 UNSUPPORTED (Flamig negative + national-program note), 2 CONTEXT (siting 4-2
no recusals; Witkos overlay). 0 substantial conflicts. Run: `python -m src.cli run --offline`.
