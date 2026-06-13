# CT Cannabis Political Check — v1.2

> **Journalistic investigative tool. LIVE ONLY — it NEVER uses synthetic, demo, or
> fabricated data.** Every name, relationship, donation, vote, and tier comes from a
> real public record and is shown with its source. There is no offline/demo report
> mode; the distributed program contains no synthetic fixtures.

> **One program, one file.** Grab **`CTCannabisPoliticalCheck_app.py`** from the
> release — it embeds every module and the real config/data files and runs on its own
> (`python3 CTCannabisPoliticalCheck_app.py`). Developers can use the package below;
> `python3 build_single_file.py` regenerates the standalone file. (The test suite uses
> fixtures purely to validate the matching/classification engine — that scaffolding is
> never bundled and never produces a report.)

**`CTCannabisPoliticalCheck`** — a reproducible Connecticut Cannabis Political
Relationship Intelligence tool. It screens **every CT state legislator (current and
former, House + Senate)** and **town officials** for cannabis-industry connections by
collecting from official public sources **and live web research**, actively
**resolving** each relationship to a confidence tier, and producing a **numbered,
source-cited PDF**.

> **This is a screening aid for humans, not an automated accusation engine.**
> Every potential link carries a source and a confidence tier; anything below
> **VERIFIED** is a lead for human review, not a finding. **"No match found" means no
> match was found in the queried sources — not proof of no involvement.**

```bash
python3 CTCannabisPoliticalCheck.py   # LIVE only — real public sources, never synthetic data
streamlit run streamlit_app.py        # web UI
```

## New in 1.2

- **LIVE ONLY — no synthetic data, ever.** Removed the offline/demo report mode. The
  program runs exclusively against real public sources; the distributed file contains
  no synthetic fixtures. (Test fixtures remain only as engine-validation scaffolding.)

## New in 1.1

- **Single-file build** — the whole program in one `CTCannabisPoliticalCheck_app.py`.
- **Years of active service** shown for every legislator (senators + reps).
- **A clickable identity-source link next to every name** (validate it is the same
  person) plus a per-row verification line.
- **Prominent verification / no-legal-implications disclaimer** on the cover and app.
- **Lobbying & money** — the cannabis-lobby section now reports disclosed contributions
  (giver → recipient, amount, date) linked to those organizations.

## New in 1.0

- **Resolved confidence tiers** — every connection is labelled **VERIFIED /
  HIGH PROBABILITY / POSSIBLE / UNVERIFIED NAME MATCH** after active resolution
  (a surname match is only a lead).
- **Campaign finance (SEEC eCRIS)** — drives the live eCRIS contribution search to
  surface cannabis-operator/principal/employee donations to legislative committees,
  linked to specific legislators with totals + sources.
- **Cannabis lobbyists (CT Office of State Ethics)** — the cannabis-industry lobbyist
  roster (data.ct.gov `4ixq-tnwe`) + any legislator-name overlap.
- **CGA roll-call votes** — ACTUAL per-member YEA/NAY on the landmark cannabis bills
  parsed from cga.ct.gov roll-call PDFs (2021 RERACA), plus a recusal/ethics check.
- **Municipal expansion** — the Simsbury / Glassman appearance-concern **category**
  generalized to every host town: a host-town roster, per-town official cannabis-tie
  leads, and **town-attorney cannabis chains** (firms that advise a town *and*
  represent cannabis interests).
- **Every line item shows its verification** (sources, or an explicit "no primary
  source located" flag); numbered, never-overwritten PDFs; **64 tests**.

---

## What it cross-references (five things, per person)

1. **Business entities (CONCORD / LLC screen)** — member/manager/agent/organizer
   appearances on any cannabis-related business in the CT Secretary of the State
   registry.
2. **DCP cannabis credentials** — licenses **and individual credentials (backer,
   key employee)**. The individual-credential rosters are mandatory: a prior
   manual pass missed an active Key Employee credential by only checking
   business/backer lists.
3. **Campaign donations** — contributions from cannabis companies, their
   owners/executives, cannabis PACs, and registered cannabis lobbyists to a
   legislator's candidate committee or leadership PAC.
4. **Registered-lobbyist family ties** — cannabis lobbyists/clients who may be
   spouses/relatives of a legislator (lead only — never a finding without
   confirmation).
5. **Spouse / family / employer cannabis ties** — confirmed via Statements of
   Financial Interests (SFI), the only legitimate source for spouse-employment.

## Quick start

```bash
make install          # install deps (pydantic, duckdb, rapidfuzz, openpyxl, reportlab, httpx, ...)
make run              # OFFLINE run against the bundled fixture corpus (zero live requests)
make run-live         # LIVE run against real data.ct.gov bulk APIs (see below)
make test             # 41 tests incl. all golden cases
make stats            # row counts from the DuckDB store
```

### Live online run

`python -m src.cli run` (no `--offline`) queries the real Connecticut Open Data
(`data.ct.gov`) bulk APIs and writes a clickable-citation PDF. Confirmed live and
wired:

| Source | Where | Live in 1.0? |
|---|---|---|
| Legislators (current + historical, back to 1915) | `data.ct.gov h2b3-nyih` | ✅ ~16.5k members |
| Cannabis establishments + retail | `data.ct.gov vw4a-3bnz` / `42yd-3x3d` | ✅ host-town map (~53 towns) |
| Business-registry ownership network (LLC→principal/agent→people) | `data.ct.gov ka36-64k6` / `qh2m-n44y` | ✅ recursive resolution |
| DCP eLicense backer / key-employee rosters | `elicense.ct.gov` | ✅ ASP.NET roster export |
| **Campaign finance** | **SEEC eCRIS contribution search** | ✅ live portal search |
| **Cannabis lobbyists** | **CT OSE `data.ct.gov 4ixq-tnwe`** | ✅ |
| **CGA roll-call votes** | **`cga.ct.gov` roll-call PDFs** | ✅ 2021 RERACA |
| **Town-attorney cannabis chains** | curated firm registry + live web | ✅ host towns |

Still **portal-only / partial** (honestly flagged as coverage gaps in the report,
never fabricated): SFI spouse-employer (OSE/FOIA), OSE contract-lobbyist client
registrations, full municipal-official rosters, and the 2012 medical-act roll-call
(different cga.ct.gov URL structure).

A live run therefore produces: the full legislator roster, the statewide cannabis
**facility→town map**, an honest **CONCORD name screen** (legislator surname
appearing in a cannabis business name, scoped to cannabis-era members, as
low-confidence REVIEW leads), and a **coverage table** stating exactly which
sources were and were not queried. Cross-referencing is scoped to members whose
service overlaps the cannabis era (`--since-year`, default 2010) — a 1915
legislator cannot have a cannabis conflict. Caching makes re-runs idempotent
(`--refresh-cache` to re-pull).

Outputs land in `out/`:

| file | contents |
|---|---|
| `out/tracker.xlsx` | working tracker — **House / Senate / Former members** sheets + "How to use" |
| `out/findings.md` / `out/findings.pdf` | ranked CONFIRMED findings + documented recusals, then a separated **UNVERIFIED LEADS** section, then the full per-member table and per-town dossiers. The **PDF** is a clean, paginated report: every citation is a clickable `[n]` marker and a numbered **References** appendix lists every source as a live, clickable URL |
| `out/review_queue.csv` | every `PROBABLE`/`POSSIBLE/REVIEW` match and every family/spouse lead, with source URLs + match explanation, for human sign-off |
| `out/conflicts.duckdb` | the full normalized store with provenance, queryable/auditable |

### CLI

```bash
python -m src.cli run [--offline] [--refresh-cache] [--since-year YYYY] [--sources a,b,c] [--db PATH]
python -m src.cli verify-sources [--online]   # confirm each source's live shape before trusting a live run
python -m src.cli stats
```

## How it works

```
collect (per-source, provenance-bearing) ─► store (DuckDB) ─► resolve (entity resolution)
   ─► analyze (CGS §1-84/§1-85, §21a-421dd + recusals) ─► report (xlsx / md / pdf / review CSV)
```

### Entity resolution (the core)

`src/resolve/matcher.py` — not a `==` on names:

* **Name normalization** (`src/normalize/names.py`): parsed name parts + generated
  variants — nicknames (Robert⇄Bob), maiden names, hyphenated/compound surnames,
  accent stripping.
* **Blocking** on surname (and surname variants) before scoring.
* **`rapidfuzz`** token-sort scoring over the full variant set + disambiguators.
* **Confidence tiers**: `CONFIRMED` (strong name **+ an independent
  disambiguator** — hometown, middle name, employer — or an authoritative filing),
  `PROBABLE`, `POSSIBLE/REVIEW`, `REJECTED`.
* **Common-surname guard**: high-collision surnames (Smith, Brown, …) never
  auto-promote above `REVIEW` without a disambiguator.
* **Never-merge guard**: protected near-collisions like **Candelaria (HD-95) vs
  Candelora (HD-86)** can never auto-merge.
* **Family leads** (uncertain relative identity) are **always** review-gated; a
  surname/town coincidence is a low-confidence lead, confirmed only by an SFI
  filing or on-the-record source.
* Every link carries a **match-explanation string** for human audit.

### Legal classification

`src/analyze/classify.py` states the standard plainly and frames (never accuses):

* **CGS §1-84 / §1-85** — a "substantial conflict" requiring recusal exists only
  where the legislator, spouse, dependent child, or an associated business (5%+
  ownership or officer/director) derives a **direct** monetary gain/loss. The
  **§1-85 "class exception"** permits voting where the interest is no greater than
  to others in the same profession — so broad industry-wide bills + small
  donations generally do **not** meet the bar (donations are surfaced as
  *Appearance concern*).
* **Conn. Gen. Stat. §21a-421dd (RERACA)** — a **sitting** legislator may not
  apply for a cannabis establishment license; a **2-year cooling-off** applies to
  **former** legislators (why the historical roster matters).
* **Documented recusals** on cannabis votes are parsed separately and surfaced at
  the top — the strongest real-world signal.

## Data sources

Every endpoint lives in **`sources.yaml`** with a `verified_on` date and per-source
toggles — **nothing is hard-coded in logic**. Collectors fail loudly
(`SourceDriftError`, naming the source + `verified_on`) if a live source changed
shape. Official **bulk / Open-Data / API** endpoints are always preferred over
scraping.

| # | Source | Where | Notes |
|---|---|---|---|
| 1 | Legislator rosters (current + historical) | `cga.ct.gov`, `data.ct.gov` (Socrata), Ballotpedia/Wikipedia fallback | name variants, committees (flags General Law & Judiciary) |
| 2 | DCP cannabis licenses **+ backer/key-employee credentials** | `data.ct.gov`, `elicense.ct.gov` roster export | individual-credential rosters are mandatory |
| 3 | Campaign finance | SEEC eCRIS, `data.ct.gov` receipts, FollowTheMoney cross-check | matched vs cannabis-donor dictionary on contributor **and** employer |
| 4 | Lobbyists | CT Office of State Ethics | flags cannabis clients + their communicators |
| 5 | Statements of Financial Interests (SFI) | CT Office of State Ethics | **only** source that confirms spouse/family employment |
| 6 | Business registry (CONCORD) | `business.ct.gov` bulk preferred; Playwright UI fallback | scraping **off by default** |

> **`verified_on` dates in `sources.yaml` are placeholders pending a human check.**
> Dataset IDs marked `PLACEHOLDER_*` must be confirmed with `verify-sources`
> before a LIVE run is trusted — the online assertions are intentionally left
> un-wired so a person verifies each live source by hand first.

## Guardrails (non-negotiable — §6 of the brief)

* **Provenance is mandatory** — every externally-sourced record carries
  `source_name`, `source_url`, `retrieved_at`; the models refuse rows without it.
* **Privacy** — the pipeline **refuses** to store home addresses, phone numbers,
  or DOBs for anyone (`config.yaml` `privacy.forbidden_fields`, enforced in the
  SFI collector and models). For family links it stores **only** the relationship
  and the cannabis-relevant fact, with its source. **Data-broker "related-to"
  inferences are never used as evidence.**
* **No auto-accusations** — every family/spouse item and every `HIT` is routed
  through the review queue before it can appear as a confirmed finding.
* **Idempotent & cached** — offline mode performs **zero** live requests (a test
  asserts this); live mode throttles per host, identifies a contact in the
  User-Agent, retries with backoff, and caches every raw response.
* **Respect ToS / robots.txt** — scraping is toggleable and **off by default**;
  bulk/API endpoints are preferred everywhere.

## Municipal / town layer (extension module)

The most consequential cannabis conflicts often sit at the **town** level. This
module extends the screen downward — to First Selectmen/Mayors, Boards of
Selectmen/Councils, **Planning & Zoning** and Zoning Boards of Appeals, town
counsel, local entities, and officials' families — and joins them to the cannabis
facilities **actually sited** in their towns. Targeting is **facility-driven**: the
host-town list is derived from cannabis-facility addresses, not a blind sweep of
all ~169 towns.

It runs automatically with `make run` (disable with `python -m src.cli run
--offline --no-municipal`) and adds a **"Town map"** sheet to `tracker.xlsx`, a
**per-town dossier** to `findings.md`, and `out/municipal_review_queue.csv`.

### The canonical pattern (Simsbury / Curaleaf)

Every town dossier is laid out in the **four output classes** the worked example
demonstrates — so the negatives are stated explicitly and nothing reads
cherry-picked:

| class | meaning | Simsbury example |
|---|---|---|
| **CONFIRMED** | well-sourced kernel | First Selectman married to a cannabis attorney (marriage + practice both primary-sourced) → **appearance concern** |
| **UNCONFIRMED** | a specific link the record does **not** support — never asserted | "spouse's firm represented the host operator" (firm's *documented* client was a *different* company) |
| **UNSUPPORTED** | checked and not found — a **negative finding** | local compost yard "handling the operator's waste" (yard bars chemicals; the only tie is an unrelated national packaging program) |
| **CONTEXT** | relevant but not a financial conflict | the state senator over the town, on the cannabis committee, with no stake |

### Connection taxonomy (§6) — each with its own evidence bar

`siting_zoning` · `official_family_rep` · `official_own_role` ·
`vendor_contractor` · `donation` · `legislative_overlay`. Every emitted link
carries its connection type, the four-class verdict, a confidence tier, source
URL(s), a one-line explanation, and a `substantial_conflict` flag.

### The two rules that make it safe

* **Primary-source gate.** A shared surname/town or a data-broker "related-to" tag
  is a **lead, never a finding**. A family/representation link promotes above
  `REVIEW` only on a **primary source** (campaign bio naming the spouse, an SFI
  spouse-employer field, a firm page naming the client, a deed/lease). The
  Glassman marriage qualifies *because the campaign bio names the spouse*; the
  Sanchez surname-coincidence does not and stays in review.
* **Limited-formal-power check.** `substantial_conflict` is set only when an
  official **both decided** (sat on the body that cast the vote) **and** has a
  shown direct gain. A First Selectman who merely *welcomed* a Zoning Commission
  approval did not control it — that is an appearance concern, not a substantial
  conflict. (Encoded in `_decided_the_siting`.)

The module's epistemic policy, printed atop every dossier: **separate the kernel
from the connective tissue; cite or drop; appearance is not accusation; negatives
are findings.**

### Municipal sources (`sources.yaml`, all `verified_on`-dated)

facility→town map · municipal-official rosters · meeting minutes (votes +
recusals; BoardDocs/CivicClerk/Granicus) · town-counsel/law-firm cannabis-client
cross-reference · land/assessor records (parcel owner ↔ official; **never a home
address**) · local campaign finance · local news (corroboration leads only).
Municipal sites are small servers — scraping is **off by default** and throttled
hard.

## Project layout

```
sources.yaml            # every endpoint + verified_on + toggles
config.yaml             # rate limits, cache, fuzzy thresholds, privacy, legal citations
src/
  config.py  models.py  donor_dict.py  pipeline.py  municipal.py  cli.py
  collectors/   # one module per source (+ municipal.py); provenance + fail-loud drift
  normalize/    # name parsing + variant generation
  resolve/      # entity resolution + confidence tiers + guards
  analyze/      # §1-84/§1-85/§21a-421dd classification, recusals, municipal taxonomy
  report/       # xlsx tracker (+ Town map), markdown/PDF (+ dossiers), review CSVs
  store/        # DuckDB schema + provenance
tests/          # golden-case + unit + integration (snapshot) + municipal tests
tests/fixtures/ # offline corpus (state golden cases + Simsbury/Curaleaf dossier)
```

## Known limitations

* **`verified_on` / dataset IDs are placeholders.** A LIVE run requires a human to
  confirm each source's current shape (`verify-sources`) and wire its
  `expected_fields` assertion. Until then, run offline against fixtures.
* **Business-registry scraping is a fallback** and disabled by default; prefer a
  `data.ct.gov` bulk business file if one exists.
* **Family/spouse ties** are only ever *leads* until an SFI filing (or other
  on-the-record source) confirms them.
* **Coverage is honestly bounded:** any source that could not be exhaustively
  queried (e.g. a rate-limited portal) is flagged; absence of a match is not
  proof of no involvement.
* Donations whose committee→member identity match is name-only are correctly held
  at `PROBABLE` (review queue), not auto-published.

## Tests

`make test` runs **64 tests**, including the brief's golden cases, the V2 feature
modules (tier relabel, SEEC campaign finance, OSE lobbyists, town-attorney chains,
CGA roll-call parsing) plus the municipal module's five (§5): the CONFIRMED
spouse-attorney appearance concern,
the UNCONFIRMED firm→host-operator non-claim, the UNSUPPORTED vendor negative, the
CONTEXT-only legislator overlay, and the surname-coincidence-vs-real-family pair.
State-level golden cases:

* DCP **key-employee** appearance surfaced even with **no** backer/business record.
* Three small dispensary donations → **Appearance concern** under §1-85.
* Family/lobbyist surname+town coincidence → **review queue**, *not* a finding —
  unless an **SFI fixture** supplies the spouse-employer confirmation.
* **Candelaria vs Candelora** never auto-merged.
* Name-variant generator (nickname/maiden/hyphenation/accents) and the confidence
  scorer, plus a full offline pipeline run diffed against a snapshot.
