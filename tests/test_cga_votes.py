"""CT General Assembly roll-call vote lookup + recusal search (V2 #5)."""
import re

from src.resolve.cga_votes import (
    CgaRollCalls, recusal_search, _surname_initial, _PAIR_RE,
)

# A trimmed mix of the two real roll-call layouts (Senate prints district+full name;
# House prints surname only, sometimes with a disambiguating initial).
_SAMPLE = ("Y 1 JOHN W. FONFARA Y 19 CATHERINE A. OSTEN N 21 KEVIN C. KELLY\n"
           "Y ABERCROMBIE N MCGORTY, B. X WOOD, K.\n")


def test_surname_initial_handles_both_layouts():
    assert _surname_initial("JOHN W. FONFARA") == ("fonfara", "j")
    assert _surname_initial("ABERCROMBIE") == ("abercrombie", "")
    assert _surname_initial("WOOD, K.") == ("wood", "k")


def test_pair_regex_extracts_vote_letter_and_name():
    pairs = _PAIR_RE.findall(re.sub(r"[ \t]+", " ", _SAMPLE))
    letters = [p[0] for p in pairs]
    assert letters.count("Y") == 3 and letters.count("N") == 2 and letters.count("X") == 1
    names = {re.sub(r"\s+", " ", p[1]).strip() for p in pairs}
    assert "KEVIN C. KELLY" in names and "ABERCROMBIE" in names


def test_offline_is_inert_and_safe():
    c = CgaRollCalls(offline=True)
    assert c.legislator_vote("Kevin Kelly") == []      # no live fetch offline
    r = recusal_search("Kevin Kelly", offline=True)
    assert r["status"] == "INSUFFICIENT DATA"


def test_legislator_vote_matches_parsed_voters(monkeypatch):
    # Drive legislator_vote with synthetic loaded bills (no network).
    c = CgaRollCalls(offline=True)
    c._loaded = True
    c.bills = [{
        "year": 2021, "bill": "HB 1201", "title": "RERACA", "era": "adult-use",
        "chamber": "House", "yea": 76, "nay": 62, "absent": 13,
        "url": "https://www.cga.ct.gov/x.PDF",
        "voters": [
            {"surname": "candelaria", "initial": "j", "vote": "Y", "raw": "CANDELARIA"},
            {"surname": "candelora", "initial": "v", "vote": "N", "raw": "CANDELORA"},
        ],
    }]
    jv = c.legislator_vote("Juan Candelaria")
    assert jv and jv[0]["vote"] == "YEA"
    vv = c.legislator_vote("Vincent Candelora")
    assert vv and vv[0]["vote"] == "NAY"
    assert c.legislator_vote("Nobody Here") == []
