"""Relationship resolution — the heart of the investigation.

A surname match is ONLY a lead. Before assigning confidence, this engine actively
tries to RESOLVE the relationship from public sources (web: news, bios, press
releases, official/company pages; plus the business registry), then classifies:

  CONFIRMED     primary-source evidence directly establishes the relationship
                (e.g. a news article naming the legislator as a cannabis owner,
                 or the registry listing them as a principal of the cannabis LLC)
  PROBABLE      multiple independent sources strongly indicate it
  POSSIBLE      some evidence suggests it but verification is incomplete
  SURNAME ONLY  only a name similarity; no relationship evidence was found

These are the INTERNAL logic strings (kept stable so the verified-resolution
cache and the matcher are unaffected). The report renders them with the
reader-facing labels in `report.build.DISPLAY_TIER`:
  CONFIRMED -> VERIFIED · PROBABLE -> HIGH PROBABILITY · POSSIBLE -> POSSIBLE ·
  SURNAME ONLY -> UNVERIFIED NAME MATCH.

Every result records exactly which searches were performed and why verification
did or did not succeed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..normalize import canonical, parse_name
from .web_search import WebResult, web_search

# Credible primary/secondary source domains (news, gov, law/company pages).
_NEWS = ("ctinsider.com", "ctmirror.org", "ctexaminer.com", "courant.com",
         "hartfordbusiness.com", "pressreader.com", "nbcconnecticut.com",
         "patch.com", "rep-am.com", "newstimes.com", "stamfordadvocate.com",
         "thehour.com", "registercitizen.com", "cannabislaw.report",
         "insideinvestigator.org", ".gov", "ballotpedia.org")
# STRONG ownership/business language (not mere co-occurrence with "cannabis").
_OWN = re.compile(r"\b(owner|owns|co-?owner|backer|backs|stake|shareholder|"
                  r"found(?:er|ed)|co-?found|principal|licensee|equity\s+(?:joint\s+)?"
                  r"venture|grows?\s+(?:it|cannabis|marijuana)|cultivat(?:e|or|ion)|"
                  r"his\s+(?:cannabis|marijuana)|her\s+(?:cannabis|marijuana))\b", re.I)
_REL = re.compile(r"\b(spouse|husband|wife|married|marry|son|daughter|brother|sister|"
                  r"father|mother|parent|child|sibling|family|relative|related|"
                  r"in-law|cousin|nephew|niece)\b", re.I)
# Contexts that mean this is NOT an ownership conflict (a different person, or just
# legislative/committee work, or a criminal case) — exclude them.
# Stems (match word variants: indict/indicted, charge/charged, traffick/trafficker).
_NEG = re.compile(r"\b(traffick|sentenc|prison|arrest|convict|smuggl|charge|"
                  r"indict|guilty|felon|seiz|raid|crimin|porn|abuse|assault|fraud|"
                  r"committee|sub-?committee|co-?chair|ranking member|vot(?:e|ed|ing)|"
                  r"bill|legislat|hearing|forum|caucus|session|amendment|testif|"
                  r"sponsor)", re.I)


@dataclass
class Evidence:
    kind: str          # self_ownership | relationship | shared_entity | same_town
    text: str
    source_url: str


@dataclass
class RelationshipResult:
    tier: str = "SURNAME ONLY"     # CONFIRMED | PROBABLE | POSSIBLE | SURNAME ONLY
    evidence: list = field(default_factory=list)
    searches: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    explanation: str = ""


def _names_in(text: str, full_name: str) -> bool:
    """Both first and last name of `full_name` appear in `text` (specific mention)."""
    p = parse_name(full_name)
    t = canonical(text)
    f, l = canonical(p.first), canonical(p.last)
    # accept nickname overlap (Art<->Arthur) via prefix
    first_ok = bool(f) and (f in t or any(w.startswith(f[:3]) for w in t.split()))
    return first_ok and bool(l) and l in t


def _domain(url: str) -> str:
    m = re.search(r"https?://([^/]+)", url or "")
    return (m.group(1) if m else "").lower()


def _credible(url: str) -> bool:
    d = _domain(url)
    return any(n in d for n in _NEWS)


_SPOUSE_PAT = [
    re.compile(r"married to ([A-Z][a-z]+(?:\s+[A-Z][a-z.'-]+){1,2})"),
    re.compile(r"(?:his|her) (?:wife|husband|spouse),?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z.'-]+){1,2})"),
    re.compile(r"\b(?:wife|husband|spouse),?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z.'-]+){1,2})"),
    re.compile(r"([A-Z][a-z]+(?:\s+[A-Z][a-z.'-]+){1,2}),?\s+(?:his|her)\s+(?:wife|husband|spouse)"),
]
_SPOUSE_STOP = {"the", "a", "an", "and", "state", "former", "republican", "democrat",
                "senator", "representative", "mayor", "first", "selectman"}


def find_spouse_names(legislator_name: str, *, offline: bool = False) -> list[str]:
    """Search the web for the legislator's spouse and extract candidate names.
    Used for the different-surname spouse cross-reference (a key conflict vector)."""
    names: list[str] = []
    seen: set[str] = set()
    for q in (f'{legislator_name} wife husband spouse',
              f'{legislator_name} married'):
        for r in web_search(q, max_results=6, offline=offline):
            for pat in _SPOUSE_PAT:
                for m in pat.finditer(r.text):
                    nm = m.group(1).strip()
                    toks = [t for t in nm.split() if t.lower() not in _SPOUSE_STOP]
                    if len(toks) < 2:
                        continue
                    nm = " ".join(toks)
                    # don't return the legislator themselves
                    if canonical(nm) == canonical(legislator_name):
                        continue
                    if canonical(nm) not in seen:
                        seen.add(canonical(nm))
                        names.append(nm)
    return names[:4]


def resolve_relationship(legislator_name: str, legislator_town: str,
                         cannabis_person: str, cannabis_entity: str,
                         cannabis_town: str = "", *, offline: bool = False,
                         registry_coowner=None) -> RelationshipResult:
    """Actively resolve whether the legislator is really connected to the cannabis
    business / principal. registry_coowner(name)->list[(biz_name,is_cannabis,url)]."""
    r = RelationshipResult()
    leg_last = canonical(parse_name(legislator_name).last)

    # ---- 1) BUSINESS-REGISTRY co-ownership (primary source) ----------------
    if registry_coowner is not None:
        try:
            for biz_name, is_cannabis, url in registry_coowner(legislator_name):
                r.searches.append(f"registry principals: '{legislator_name}'")
                if is_cannabis:
                    r.evidence.append(Evidence(
                        "shared_entity",
                        f"Business Registry lists {legislator_name} as a principal of "
                        f"cannabis-linked business '{biz_name}'", url))
                    r.sources.append(url)
        except Exception:  # noqa: BLE001
            pass

    # ---- 2) WEB verification (news / bios / company pages) -----------------
    queries = [
        f'{legislator_name} cannabis Connecticut',
        f'{legislator_name} {cannabis_entity}',
        f'{legislator_name} cannabis owner OR license OR backer',
        f'{legislator_name} spouse OR husband OR wife OR family',
        f'{cannabis_person} {legislator_name}',
    ]
    seen_urls: set[str] = set()
    for q in queries:
        r.searches.append(f"web: {q}")
        for res in web_search(q, max_results=6, offline=offline):
            if res.url in seen_urls:
                continue
            seen_urls.add(res.url)
            text = res.text
            mentions_leg = _names_in(text, legislator_name)
            has_own = bool(_OWN.search(text))
            has_rel = bool(_REL.search(text))
            has_neg = bool(_NEG.search(text))   # crime / pure-legislative context
            cred = _credible(res.url)
            tl = text.lower()
            # cannabis context = the generic cannabis terms OR a DISTINCTIVE word from
            # the business name (>=5 chars, not generic). Using a short token like "ct"
            # from "CT BGP LLC" would match almost any text -> false positives.
            _GEN = {"cannabis", "marijuana", "holdings", "group", "ventures",
                    "company", "connecticut", "social", "equity", "partners"}
            ent_words = [re.escape(w) for w in cannabis_entity.lower().split()
                         if len(w) >= 5 and w not in _GEN]
            ctx_pat = (r"cannabis|marijuana|dispensar|cultivat"
                       + ("|" + "|".join(ent_words[:2]) if ent_words else ""))
            cannabis_ctx = bool(re.search(ctx_pat, tl))
            cp_first = (cannabis_person.split()[0].lower() if cannabis_person else "")
            mentions_cp = bool(cp_first) and cp_first in tl
            if mentions_leg and has_own and cred and cannabis_ctx and not has_neg:
                # Legislator named with STRONG cannabis-OWNERSHIP language in a credible
                # source, and NOT a crime/legislative-work context (different person /
                # committee work would be a false positive).
                r.evidence.append(Evidence("self_ownership",
                    f"{res.title} — “{res.snippet[:200]}”", res.url))
                r.sources.append(res.url)
            elif mentions_leg and has_rel and (mentions_cp or cannabis_ctx) and cred \
                    and not has_neg:
                # A family relationship tied specifically to the cannabis person/business.
                r.evidence.append(Evidence("relationship",
                    f"{res.title} — “{res.snippet[:200]}”", res.url))
                r.sources.append(res.url)

    # ---- 3) town corroboration (already-known public residence) ------------
    if cannabis_town and legislator_town and \
            canonical(cannabis_town) == canonical(legislator_town):
        r.evidence.append(Evidence("same_town",
            f"cannabis principal's residence town ({cannabis_town}) matches the "
            f"official's town", ""))

    # ---- 4) classify -------------------------------------------------------
    self_own = [e for e in r.evidence if e.kind in ("self_ownership", "shared_entity")]
    rel = [e for e in r.evidence if e.kind == "relationship"]
    own_domains = {_domain(e.source_url) for e in self_own if e.source_url}
    rel_domains = {_domain(e.source_url) for e in rel if e.source_url}

    if any(e.kind == "shared_entity" for e in r.evidence) or len(own_domains) >= 2:
        r.tier = "CONFIRMED"
        r.explanation = ("Primary sources establish that the official is directly tied "
                         "to the cannabis business (registry principal and/or multiple "
                         "news sources naming them as an owner/backer).")
    elif len(own_domains) == 1 or len(rel_domains) >= 2:
        r.tier = "PROBABLE"
        r.explanation = ("Independent source(s) indicate a real cannabis ownership or "
                         "family relationship; confirm with a second primary source.")
    elif rel or any(e.kind == "same_town" for e in r.evidence):
        r.tier = "POSSIBLE"
        r.explanation = ("Some evidence (a relationship mention or a matching residence "
                         "town) suggests a connection, but it is not yet verified.")
    else:
        r.tier = "SURNAME ONLY"
        r.explanation = (f"Searched the web (news, bios, company pages) and the business "
                         f"registry for any tie between {legislator_name} and "
                         f"{cannabis_person}/{cannabis_entity}; NO relationship or "
                         f"ownership evidence was found. This is a name coincidence "
                         f"unless a human finds a non-public source.")
    # de-dup sources
    r.sources = sorted(set(s for s in r.sources if s))
    return r
