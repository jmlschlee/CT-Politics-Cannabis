"""Resolve the cannabis OWNERSHIP NETWORK from the CT Business Registry.

CT cannabis licensees are usually LLCs owned by other LLCs (e.g. FFD WEST LLC ->
FFD HOLDINGS LLC -> ... -> individuals). To map influence we must walk that chain
down to actual PEOPLE. This module:

  1. matches cannabis business names -> Business Master ids (n7gp-d28j),
  2. pulls Principals (ka36-64k6) and Agents (qh2m-n44y) by business_id,
  3. recursively resolves any CORPORATE principal to its own principals,
  4. emits the terminal PERSON principals/agents as CannabisPerson records, plus
     the ownership edges for the network section.

PRIVACY (§8): the Principals/Agents datasets carry RESIDENCE (home) addresses. We
NEVER store them — only the person name, role, the cannabis entity, the business
city (municipality), and the filing date are kept.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..models import CannabisPerson, Provenance
from ..normalize import canonical

MASTER = "n7gp-d28j"
PRINCIPALS = "ka36-64k6"
AGENTS = "qh2m-n44y"
_BIZ_URL = "https://data.ct.gov/d/{}"

# Tokens that mark a "principal" as a company rather than a person.
_CORP_RE = re.compile(
    r"\b(LLC|L\.L\.C|INC|CORP|CO|COMPANY|LP|LLP|PLLC|LTD|HOLDINGS|GROUP|"
    r"VENTURES|PARTNERS|TRUST|FOUNDATION|ASSOCIATES|ENTERPRISES|MANAGEMENT|"
    r"CAPITAL|REALTY|PROPERTIES|INVESTMENTS|N\.A|BANK)\b", re.IGNORECASE)


def _is_corporate(name: str, first: str, last: str) -> bool:
    if _CORP_RE.search(name or ""):
        return True
    # No personal first+last -> treat as an organization.
    return not (first and last)


def _chunks(seq, n):
    seq = list(seq)
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _q(values) -> str:
    """SoQL IN-list with escaped single quotes."""
    return ", ".join("'" + str(v).replace("'", "''") + "'" for v in values)


@dataclass
class OwnershipEdge:
    root_entity: str       # the licensed cannabis business at the top of the chain
    parent: str            # the business whose principal/agent this is
    person_or_org: str     # principal/agent name
    role: str              # principal | agent
    is_person: bool
    depth: int
    business_city: str = ""
    residence_city: str = ""      # public registry residence town (identity signal)
    residence_address: str = ""   # public registry residence address
    date: str = ""                # filing/registration date (record date)
    license_type: str = ""        # cannabis license category of the root entity
    license_number: str = ""
    source_url: str = ""
    business_url: str = ""


@dataclass
class NetworkResult:
    persons: list[CannabisPerson] = field(default_factory=list)
    edges: list[OwnershipEdge] = field(default_factory=list)
    matched_entities: int = 0
    unmatched_entities: list[str] = field(default_factory=list)
    queried: bool = False
    note: str = ""


def _get(dataset: str, where: str, fast_delay: float, select: str | None = None):
    from .live_socrata import socrata_get
    return socrata_get("data.ct.gov", dataset, where=where, select=select,
                       page_size=50000, _delay=fast_delay)


def resolve_cannabis_network(entity_names: list[str], *, max_depth: int = 3,
                             fast_delay: float = 0.4, retrieved_date: str = "",
                             license_map: dict | None = None) -> NetworkResult:
    """Walk the ownership chain for each cannabis business name down to people,
    retaining public address/date fields. `license_map` maps an upper-cased business
    name to (license_type, license_number) for stamping the cannabis category."""
    res = NetworkResult(queried=True)
    license_map = {(k or "").upper(): v for k, v in (license_map or {}).items()}
    names = sorted({n.strip() for n in entity_names if n and n.strip()})
    if not names:
        res.note = "no cannabis business names to resolve"
        return res

    # name(upper) -> business id(s) ; ids carry name + registration date
    name_to_ids: dict[str, list[str]] = {}
    id_to_name: dict[str, str] = {}
    id_to_regdate: dict[str, str] = {}
    for chunk in _chunks([n.upper() for n in names], 60):
        try:
            rows = _get(MASTER, f"upper(name) in ({_q(chunk)})", fast_delay,
                        select="id,name,status,date_registration")
        except Exception as e:  # noqa: BLE001
            res.note = f"business master lookup failed: {e}"
            return res
        for r in rows:
            nm = (r.get("name") or "").upper()
            bid = r.get("id")
            if not bid:
                continue
            name_to_ids.setdefault(nm, []).append(bid)
            id_to_name[bid] = r.get("name") or nm
            rd = (r.get("date_registration") or "")[:10]
            id_to_regdate[bid] = "" if rd.startswith("0001") else rd

    matched = {n for n in names if n.upper() in name_to_ids}
    res.matched_entities = len(matched)
    res.unmatched_entities = sorted(n for n in names if n.upper() not in name_to_ids)

    # BFS over ownership, root = each licensed cannabis business.
    # frontier: list of (business_id, root_entity_name, parent_name, depth)
    frontier = []
    for n in matched:
        for bid in name_to_ids[n.upper()]:
            frontier.append((bid, id_to_name.get(bid, n), id_to_name.get(bid, n), 0))
    seen_ids: set[str] = set()
    prov = Provenance(source_name="business_registry",
                      source_url=_BIZ_URL.format(PRINCIPALS))

    while frontier:
        depth = frontier[0][3]
        if depth >= max_depth:
            break
        layer = [f for f in frontier if f[3] == depth and f[0] not in seen_ids]
        frontier = [f for f in frontier if f[3] != depth]
        for f in layer:
            seen_ids.add(f[0])
        if not layer:
            continue
        ids = [f[0] for f in layer]
        meta = {f[0]: f for f in layer}
        # Pull principals + agents for this layer (batched by business_id).
        for dataset, role in ((PRINCIPALS, "principal"), (AGENTS, "agent")):
            for chunk in _chunks(ids, 60):
                try:
                    rows = _get(dataset, f"business_id in ({_q(chunk)})", fast_delay)
                except Exception as e:  # noqa: BLE001
                    res.note = f"{role} lookup failed at depth {depth}: {e}"
                    rows = []
                for r in rows:
                    bid = r.get("business_id")
                    root = meta.get(bid, (None, "", "", depth))[1]
                    parent = id_to_name.get(bid, meta.get(bid, (None, "", "", 0))[2])
                    nm = (r.get("name__c") or "").strip()
                    if not nm:
                        continue
                    first = (r.get("firstname") or "").strip()
                    last = (r.get("lastname") or "").strip()
                    is_org = _is_corporate(nm, first, last)
                    # public address/date fields (kept — public record + identity signal)
                    res_city = (r.get("residence_city") or "").title()
                    res_addr = (r.get("residence_address") or
                                r.get("residence_street_address_1") or "").strip()
                    biz_city = (r.get("business_city") or "").title()
                    root_ids = name_to_ids.get((root or "").upper(), [])
                    # the cannabis LICENSE business's registration date (for the lead)
                    root_reg = id_to_regdate.get(root_ids[0], "") if root_ids else ""
                    # this specific filing's own registration date (per-record, NOT the
                    # data-load create_dt — that was identical for every row, misleading)
                    rec_date = id_to_regdate.get(bid, "")
                    lic = license_map.get((root or "").upper(), ("", ""))
                    edge = OwnershipEdge(
                        root_entity=root, parent=parent, person_or_org=nm, role=role,
                        is_person=not is_org, depth=depth, business_city=biz_city,
                        residence_city=res_city, residence_address=res_addr,
                        date=rec_date,    # per-record filing date (blank if unknown)
                        license_type=lic[0], license_number=lic[1],
                        source_url=_BIZ_URL.format(dataset),
                        business_url=_BIZ_URL.format(MASTER))
                    res.edges.append(edge)
                    if not is_org:
                        # Terminal PERSON — a real human behind the cannabis business.
                        res.persons.append(CannabisPerson(
                            cp_id=f"breg::{bid}::{canonical(nm)}::{role}",
                            full_name=nm, role=role,
                            credential_type=f"business-{role}",
                            entity_name=root, source_kind="business",
                            residence_city=res_city, residence_address=res_addr,
                            business_city=biz_city, license_type=lic[0],
                            license_number=lic[1], registration_date=root_reg,
                            retrieved_date=retrieved_date,
                            business_url=_BIZ_URL.format(MASTER),
                            provenance=prov))
                    else:
                        # Corporate principal — resolve its own master id next layer.
                        res._pending = getattr(res, "_pending", [])
                        res._pending.append((nm, root, depth + 1))
        # Resolve pending corporate names -> ids for the next layer.
        pending = getattr(res, "_pending", [])
        res._pending = []
        if pending and depth + 1 < max_depth:
            upper_names = sorted({p[0].upper() for p in pending})
            for chunk in _chunks(upper_names, 60):
                try:
                    rows = _get(MASTER, f"upper(name) in ({_q(chunk)})", fast_delay,
                                select="id,name")
                except Exception:  # noqa: BLE001
                    rows = []
                for r in rows:
                    bid, nm = r.get("id"), (r.get("name") or "")
                    if not bid or bid in seen_ids:
                        continue
                    id_to_name[bid] = nm
                    # carry the root of the first pending entry matching this name
                    root = next((p[1] for p in pending if p[0].upper() == nm.upper()), nm)
                    frontier.append((bid, root, nm, depth + 1))
    return res
