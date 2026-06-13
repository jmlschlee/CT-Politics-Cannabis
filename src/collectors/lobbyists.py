"""CT Office of State Ethics registered lobbyists (communicators) + clients.
Flags cannabis-industry clients and their communicators."""
from __future__ import annotations

from ..analyze.cannabis_terms import is_cannabis_text
from ..models import Lobbyist
from .base import Collector, provenance_for


class LobbyistsCollector(Collector):
    source_name = "lobbyists"
    fixture_name = "lobbyists"
    live_available = False
    live_unavailable_reason = (
        "CT registered lobbyists live on the Office of State Ethics portal, not a "
        "data.ct.gov bulk API; live collection requires that portal (scrape, off).")

    def parse(self, raw) -> list[Lobbyist]:
        url = self.src.get("office_of_state_ethics", {}).get(
            "base_url", "https://www.ethics.ct.gov")
        markers = [m.lower() for m in self.src.get("cannabis_client_markers", [])]
        out: list[Lobbyist] = []
        for d in raw:
            client = d.get("client_name", "")
            is_can = d.get("is_cannabis")
            if is_can is None:
                is_can = is_cannabis_text(client) or any(m in client.lower() for m in markers)
            out.append(Lobbyist(
                lobbyist_id=d["lobbyist_id"],
                communicator_name=d["communicator_name"],
                client_name=client, is_cannabis=bool(is_can),
                registration_year=d.get("registration_year"),
                hometown=d.get("hometown", d.get("town", "")),
                provenance=provenance_for(self.source_name, d.get("source_url", url)),
            ))
        return out
