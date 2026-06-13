"""CT Cannabis Political Check — Streamlit front end.

A screening aid for humans, NOT an automated accusation engine. Cross-references CT
legislators and town officials against cannabis-industry connections (business
registry ownership, DCP eLicense rosters, SEEC campaign finance, OSE lobbyists,
cga.ct.gov roll-call votes, municipal town-attorney chains), actively resolves each
relationship, and produces a numbered, source-cited PDF.

Run locally:  streamlit run streamlit_app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="CT Cannabis Political Check",
                   page_icon="🌿", layout="centered")

# ---- light, readable theme (defensive against viewer dark mode) ----
st.markdown("""
<style>
:root { color-scheme: light; }
.stApp { background:#f6f8f6; color:#16271d; }
h1,h2,h3,h4,p,li,div,span,label { color:#16271d !important; }
.block-container { max-width: 760px; }
.stButton>button { background:#16412b; color:#fff !important; border:0;
  font-weight:600; border-radius:6px; padding:.5rem 1.1rem; }
.cap { color:#5b6b60 !important; font-size:.86rem; }
.badge { display:inline-block; background:#e6efe9; color:#16412b !important;
  border-radius:10px; padding:2px 10px; font-size:.78rem; font-weight:600; }
</style>
""", unsafe_allow_html=True)

try:
    from src.report import DISPLAY_NAME
    from src.report.build import app_version  # type: ignore
    _ver = app_version()
except Exception:  # noqa: BLE001
    DISPLAY_NAME = "CT Cannabis Political Check"
    _ver = "1.0"

st.title("🌿 CT Cannabis Political Check")
st.markdown(f"<span class='badge'>v{_ver}</span> &nbsp; "
            "<span class='cap'>A screening aid for humans — <b>not</b> an automated "
            "accusation engine.</span>", unsafe_allow_html=True)
st.write(
    "Cross-references Connecticut legislators and town officials against "
    "cannabis-industry connections from official public sources — the state business "
    "registry ownership network, DCP eLicense backer/key-employee rosters, **SEEC "
    "campaign-finance** contributions, **OSE cannabis lobbyists**, **cga.ct.gov "
    "roll-call votes**, and **municipal town-attorney chains** — actively resolves "
    "each relationship to a confidence tier (VERIFIED / HIGH PROBABILITY / POSSIBLE / "
    "UNVERIFIED NAME MATCH), and produces a numbered, source-cited PDF.")

st.divider()

mode = st.radio(
    "Run mode",
    ["Offline demo (fast, bundled fixtures)",
     "Live (data.ct.gov + web) — slower, may exceed free-tier limits"],
    index=0)
offline = mode.startswith("Offline")

if not offline:
    st.warning("A live run fetches ~16k legislators plus live web/SEEC/OSE/CGA "
               "lookups and can take several minutes — it may exceed hosted free-tier "
               "memory/time. For a quick look, use the offline demo.")

if st.button("Run screening"):
    with st.spinner("Running the screening pipeline…"):
        try:
            from src.config import config
            from src.pipeline import Pipeline
            from src.municipal import MunicipalPipeline
            from src.report import finalize_report

            result = Pipeline(offline=offline).run()
            municipal = MunicipalPipeline(offline=offline).run()
            rep = finalize_report(result, config(), municipal=municipal,
                                  push_to_downloads=False)
        except Exception as e:  # noqa: BLE001
            st.error(f"Run failed: {e}")
            st.stop()

    c = result.counts
    st.success(f"Report #{rep['number']} generated "
               f"({'OFFLINE demo' if offline else 'LIVE'}).")
    a, b, d = st.columns(3)
    a.metric("Legislators", f"{c.get('legislators', 0):,}")
    b.metric("Cannabis people", f"{c.get('cannabis_persons', 0):,}")
    d.metric("Connections (V/HP/P)",
             c.get("confirmed_findings", 0) + c.get("probable_findings", 0)
             + c.get("possible_findings", 0))
    a2, b2, d2 = st.columns(3)
    a2.metric("SEEC contributions", c.get("cannabis_contributions", 0))
    b2.metric("Cannabis lobbyists", c.get("cannabis_lobbyists", 0))
    d2.metric("Host towns", municipal.counts.get("host_towns", 0))

    leads = [x for x in getattr(result, "legislator_cannabis_leads", [])
             if x.get("confidence") in ("CONFIRMED", "PROBABLE", "POSSIBLE")]
    if leads:
        from src.report.build import display_tier
        st.subheader("Resolved legislator cannabis connections")
        st.table([{"Legislator": x["person"],
                   "Tier": display_tier(x.get("confidence")),
                   "Cannabis tie": f"{x['cannabis_person']} / {x['cannabis_entity']}"}
                  for x in leads[:25]])

    pdf = rep.get("report_pdf")
    if pdf and Path(pdf).exists():
        st.download_button("⬇️ Download the full PDF report",
                           data=Path(pdf).read_bytes(),
                           file_name=Path(pdf).name, mime="application/pdf")

st.divider()
st.markdown("<span class='cap'>Every potential link carries a source and a confidence "
            "tier; anything below VERIFIED is a lead for human review, not a finding. "
            "Absence of a match is “no match found,” never proof of no involvement."
            "</span>", unsafe_allow_html=True)
