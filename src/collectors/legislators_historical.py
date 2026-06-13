"""Former CT legislators (historical sessions). The 2-year §21a-421dd cooling-off
period makes former members in-scope for cannabis-license screening."""
from __future__ import annotations

from ..models import Legislator
from .base import Collector
from .legislators_current import roster_to_legislator


class LegislatorsHistoricalCollector(Collector):
    source_name = "legislators_historical"
    fixture_name = "legislators_historical"

    def fetch_live(self) -> list:
        # Live, the full historical roster is loaded by legislators_current from the
        # same h2b3-nyih dataset (with is_former computed per row). No-op here.
        return []

    def parse(self, raw) -> list[Legislator]:
        url = self.src.get("cga_session_index", "https://www.cga.ct.gov")
        return [roster_to_legislator(d, self.source_name, url, is_former=True)
                for d in raw]
