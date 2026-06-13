"""Shared cannabis-industry term markers used to flag entities/clients/employers."""
from __future__ import annotations

import re

CANNABIS_MARKERS = [
    "cannabis", "marijuana", "marihuana", "cannabinoid", "thc", "cbd",
    "dispensary", "cultivat", "micro-cultivat", "microcultivat",
    "hemp", "hybrid genetics", "weed", "ganja", "budtender",
    "product manufacturer", "marijuana policy project",
]

# Match each marker at a WORD BOUNDARY (a stem is still allowed at the end, so
# "cultivat" keeps catching "cultivation"). A plain substring test mis-fires on the
# short markers — "thc" inside "healTHCare", or "cbd"/"hemp" buried mid-word — which
# produced false cannabis hits on healthcare lobbyists. The leading \b stops that.
_MARKER_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(m) for m in CANNABIS_MARKERS) + r")", re.I)


def is_cannabis_text(text: str | None) -> bool:
    if not text:
        return False
    return bool(_MARKER_RE.search(text))
