"""Name parsing, canonicalization, and variant generation.

The matcher's recall depends on this: a legislator "Robert J. Smith-Jones" must
be findable as "Bob Smith", "Bobby Jones", maiden names, accent-stripped, etc.
Pure-stdlib so it is trivially testable offline.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# Common nickname <-> formal-name groups. Bidirectional within a group.
NICKNAME_GROUPS: list[set[str]] = [
    {"robert", "rob", "bob", "bobby", "robbie"},
    {"william", "will", "bill", "billy", "willie"},
    {"richard", "rich", "rick", "ricky", "dick"},
    {"christopher", "chris", "topher"},
    {"michael", "mike", "mick", "mickey"},
    {"james", "jim", "jimmy", "jamie"},
    {"john", "jack", "johnny", "jon"},
    {"joseph", "joe", "joey"},
    {"thomas", "tom", "tommy"},
    {"charles", "charlie", "chuck", "chas"},
    {"daniel", "dan", "danny"},
    {"matthew", "matt", "matty"},
    {"anthony", "tony"},
    {"david", "dave", "davy"},
    {"edward", "ed", "eddie", "ted", "teddy"},
    {"steven", "stephen", "steve"},
    {"andrew", "andy", "drew"},
    {"katherine", "catherine", "kate", "katie", "kathy", "cathy", "kat"},
    {"elizabeth", "liz", "beth", "betty", "eliza", "lizzie"},
    {"margaret", "maggie", "meg", "peg", "peggy"},
    {"patricia", "pat", "patty", "trish"},
    {"jennifer", "jen", "jenny"},
    {"deborah", "debra", "deb", "debbie"},
    {"susan", "sue", "susie"},
    {"jessica", "jess"},
    {"rebecca", "becca", "becky"},
    {"nicholas", "nick", "nicky"},
    {"benjamin", "ben", "benji"},
    {"alexander", "alex", "alexandra", "sandy", "lex"},
    {"samuel", "sam", "sammy", "samantha"},
    {"gregory", "greg"},
    {"vincent", "vince", "vinny"},
    {"raymond", "ray"},
    {"theresa", "teresa", "terri", "terry"},
    {"francis", "frank", "frances", "fran", "frankie"},
]

_NICK_INDEX: dict[str, set[str]] = {}
for _g in NICKNAME_GROUPS:
    for _name in _g:
        _NICK_INDEX.setdefault(_name, set()).update(_g - {_name})

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
_PUNCT = re.compile(r"[.,]")
_WS = re.compile(r"\s+")


def strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def clean(text: str) -> str:
    text = strip_accents(text or "")
    text = _PUNCT.sub(" ", text)
    text = _WS.sub(" ", text).strip()
    return text


def canonical(text: str) -> str:
    """Lowercased, accent-stripped, de-punctuated — for blocking/comparison keys."""
    return clean(text).lower()


@dataclass
class NameParts:
    first: str = ""
    middle: str = ""
    last: str = ""
    suffix: str = ""
    nicknames: list[str] = field(default_factory=list)   # found in quotes/parens
    raw: str = ""

    @property
    def full(self) -> str:
        bits = [self.first, self.middle, self.last]
        out = " ".join(b for b in bits if b)
        if self.suffix:
            out = f"{out} {self.suffix}"
        return out.strip()


def _extract_quoted_nick(raw: str) -> tuple[str, list[str]]:
    """Pull out 'Bob' / (Bob) style nicknames, returning (cleaned, [nicks])."""
    nicks = re.findall(r'["“‘\'(]([A-Za-z]+)[")”’\']', raw)
    cleaned = re.sub(r'["“‘\'(][A-Za-z]+[")”’\']', " ", raw)
    return cleaned, [n.lower() for n in nicks]


def parse_name(raw: str) -> NameParts:
    """Parse 'Last, First Middle' or 'First Middle Last Suffix' into parts."""
    raw = raw or ""
    work, nicks = _extract_quoted_nick(raw)

    if "," in work:
        # "Last, First Middle [Suffix]"
        last_part, _, rest = work.partition(",")
        tokens = clean(rest).split()
        last_tokens = clean(last_part).split()
    else:
        tokens = clean(work).split()
        last_tokens = []

    suffix = ""
    if tokens and tokens[-1].lower().strip(".").rstrip(".") in SUFFIXES:
        suffix = tokens.pop().lower().strip(".")
    if last_tokens and last_tokens[-1].lower().strip(".") in SUFFIXES:
        suffix = last_tokens.pop().lower().strip(".")

    if last_tokens:  # comma form
        first = tokens[0] if tokens else ""
        middle = " ".join(tokens[1:]) if len(tokens) > 1 else ""
        last = " ".join(last_tokens)
    else:            # space form
        if len(tokens) == 0:
            first = middle = last = ""
        elif len(tokens) == 1:
            first, middle, last = tokens[0], "", ""
        elif len(tokens) == 2:
            first, middle, last = tokens[0], "", tokens[1]
        else:
            first, middle, last = tokens[0], " ".join(tokens[1:-1]), tokens[-1]

    return NameParts(
        first=first, middle=middle, last=last, suffix=suffix,
        nicknames=nicks, raw=raw,
    )


def surname_key(name_or_parts: str | NameParts) -> str:
    """Blocking key: the canonical last name. For hyphenated/compound surnames,
    the FIRST component is the primary key (variants cover the rest)."""
    parts = name_or_parts if isinstance(name_or_parts, NameParts) else parse_name(name_or_parts)
    last = canonical(parts.last)
    if not last:
        return ""
    # split on hyphen or space -> primary component
    return re.split(r"[\s\-]+", last)[0]


def _hyphen_components(last: str) -> list[str]:
    return [c for c in re.split(r"[\s\-]+", canonical(last)) if c]


def name_variants(raw: str, maiden: str | None = None) -> list[str]:
    """Generate canonical full-name variants for recall:
    - accent-stripped baseline
    - nickname <-> formal first-name swaps (both directions)
    - explicit quoted nicknames
    - hyphenated/compound surname components used alone
    - optional maiden surname
    Returns a de-duplicated, order-stable list of canonical strings.
    """
    parts = parse_name(raw)
    firsts = {canonical(parts.first)} if parts.first else {""}
    # quoted nicks
    for nk in parts.nicknames:
        firsts.add(canonical(nk))
    # nickname expansions
    base_firsts = set(firsts)
    for f in base_firsts:
        for alt in _NICK_INDEX.get(f, ()):  # type: ignore[arg-type]
            firsts.add(alt)
    firsts = {f for f in firsts if f} or {""}

    lasts: set[str] = set()
    if parts.last:
        lasts.add(canonical(parts.last))
        for comp in _hyphen_components(parts.last):
            lasts.add(comp)
    if maiden:
        lasts.add(canonical(maiden))
    lasts = {l for l in lasts if l}

    variants: list[str] = []
    seen: set[str] = set()
    mid = canonical(parts.middle)
    for f in sorted(firsts):
        for l in sorted(lasts):
            for use_mid in ([mid, ""] if mid else [""]):
                v = " ".join(x for x in [f, use_mid, l] if x).strip()
                if v and v not in seen:
                    seen.add(v)
                    variants.append(v)
    return variants
