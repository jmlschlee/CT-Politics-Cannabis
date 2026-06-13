"""Cannabis-donor dictionary: the set of names that mark a contribution as
cannabis-affiliated — license-holder businesses, their owners/executives,
cannabis PACs, and registered cannabis lobbyists. Contributions are matched
against this dictionary on BOTH the contributor name AND the employer/occupation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .analyze.cannabis_terms import is_cannabis_text
from .models import CannabisEntity, CannabisPerson, Contribution, Lobbyist
from .normalize import canonical


@dataclass
class DonorDict:
    names: set[str] = field(default_factory=set)        # canonical cannabis names
    labels: dict[str, str] = field(default_factory=dict)  # canonical -> display label

    def add(self, name: str, label: str) -> None:
        c = canonical(name)
        if c:
            self.names.add(c)
            self.labels.setdefault(c, label)

    def is_cannabis_contribution(self, contrib: Contribution) -> tuple[bool, str]:
        """Return (is_cannabis, why)."""
        for field_val, lbl in ((contrib.contributor_name, "contributor"),
                               (contrib.employer, "employer")):
            c = canonical(field_val)
            if c and c in self.names:
                return True, f"{lbl} '{field_val}' is in the cannabis-donor dictionary"
        # textual fallback (e.g. an obviously cannabis employer not yet in the dict)
        if is_cannabis_text(contrib.employer) or is_cannabis_text(contrib.contributor_name):
            return True, "contributor/employer text matches cannabis-industry markers"
        if is_cannabis_text(contrib.occupation):
            return True, f"occupation '{contrib.occupation}' matches cannabis markers"
        return False, ""


def build_donor_dict(entities: list[CannabisEntity],
                     persons: list[CannabisPerson],
                     lobbyists: list[Lobbyist]) -> DonorDict:
    dd = DonorDict()
    for e in entities:
        dd.add(e.name, f"cannabis business: {e.name}")
    for p in persons:
        dd.add(p.full_name, f"{p.role or 'principal'} of cannabis business "
                            f"{p.entity_name or '(unnamed)'}")
    for lob in lobbyists:
        if lob.is_cannabis:
            dd.add(lob.communicator_name,
                   f"registered cannabis lobbyist (client: {lob.client_name})")
            dd.add(lob.client_name, f"cannabis lobby client: {lob.client_name}")
    return dd
