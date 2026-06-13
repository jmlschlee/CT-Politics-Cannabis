"""Parse documented recusals on cannabis votes from House/Senate journals,
General Law / Judiciary committee records, and Office of State Ethics
declarations. A documented recusal is the STRONGEST real-world signal — it is a
finding in its own right, surfaced at the top of the report.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .cannabis_terms import is_cannabis_text

# Phrasings that indicate a member declared a conflict / recused.
_RECUSAL_CUES = [
    r"recus(?:e|ed|al)",
    r"declar(?:e|ed)\s+(?:a\s+)?(?:potential\s+)?conflict",
    r"abstain(?:ed|s|ing)?",
    r"did not vote.*conflict",
    r"statement of (?:potential )?conflict",
]
_CUE_RE = re.compile("|".join(_RECUSAL_CUES), re.IGNORECASE)
# A bill/subject is cannabis-related if the surrounding text mentions cannabis.


@dataclass
class Recusal:
    member_name: str
    chamber: str
    date: str
    subject: str
    source_name: str
    source_url: str
    snippet: str


def parse_recusals(records: list[dict]) -> list[Recusal]:
    """`records` are normalized journal/committee/ethics entries:
       {member_name, chamber, date, subject, text, source_name, source_url}.
    Emits a Recusal only when BOTH a recusal cue AND cannabis context appear —
    so we never invent a recusal from a generic abstention.
    """
    out: list[Recusal] = []
    for r in records:
        text = r.get("text", "") or ""
        subject = r.get("subject", "") or ""
        context = f"{subject}\n{text}"
        if not _CUE_RE.search(context):
            continue
        if not (is_cannabis_text(subject) or is_cannabis_text(text)):
            continue
        m = _CUE_RE.search(context)
        snippet = context[max(0, m.start() - 60): m.end() + 80].strip()
        out.append(Recusal(
            member_name=r.get("member_name", ""),
            chamber=r.get("chamber", ""),
            date=r.get("date", ""),
            subject=subject or "(cannabis matter)",
            source_name=r.get("source_name", ""),
            source_url=r.get("source_url", ""),
            snippet=snippet,
        ))
    return out
