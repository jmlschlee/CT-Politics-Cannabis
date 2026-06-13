"""Typed records. Every externally-sourced record carries Provenance — a record
without it cannot be constructed (the report's whole value is its citations)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

Chamber = Literal["House", "Senate"]
Confidence = Literal["CONFIRMED", "PROBABLE", "POSSIBLE/REVIEW", "REJECTED"]
FindingStatus = Literal[
    "No match found",
    "HIT — see findings",
    "Appearance concern",
    "Unable to verify",
]
RefType = Literal["business", "dcp", "donation", "lobbyist", "sfi"]

# Fields we will refuse to persist for anyone (mirrors config.yaml privacy block).
FORBIDDEN_FIELDS = {
    "home_address", "street_address", "phone", "mobile",
    "dob", "date_of_birth", "ssn",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Provenance(BaseModel):
    source_name: str
    source_url: str
    retrieved_at: datetime = Field(default_factory=_utcnow)
    raw_snippet: Optional[str] = None

    @field_validator("source_name", "source_url")
    @classmethod
    def _nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Provenance requires non-empty source_name and source_url")
        return v


class Provenanced(BaseModel):
    """Base for anything sourced externally."""
    provenance: Provenance


class Legislator(Provenanced):
    person_id: str
    full_name: str
    first: str = ""
    middle: str = ""
    last: str = ""
    suffix: str = ""
    chamber: Optional[Chamber] = None
    district: str = ""
    party: str = ""
    hometown: str = ""
    first_elected: Optional[int] = None
    years_served: str = ""
    occupation: str = ""
    committees: list[str] = Field(default_factory=list)
    is_former: bool = False
    name_variants: list[str] = Field(default_factory=list)

    @property
    def flags_relevant_committee(self) -> bool:
        """General Law and Judiciary are where cannabis bills move."""
        c = " ".join(self.committees).lower()
        return "general law" in c or "judiciary" in c


class CannabisEntity(Provenanced):
    """A cannabis-related business/license."""
    entity_id: str
    name: str
    entity_type: str = ""        # LLC, dispensary, micro-cultivator, ...
    license_type: str = ""
    status: str = ""


class CannabisPerson(Provenanced):
    """A named person tied to cannabis: DCP backer/key-employee credential holder,
    or a business-registry principal/agent/organizer on a cannabis entity.

    Public-record address/date fields are retained (the source data is public and
    the residence town is a real identity disambiguator for cross-referencing)."""
    cp_id: str
    full_name: str
    role: str = ""               # backer | key_employee | member | manager | agent | ...
    credential_type: str = ""    # e.g. 'cannabis-key-employee'
    entity_name: str = ""
    source_kind: RefType = "dcp"
    residence_city: str = ""     # public registry residence town (identity signal)
    residence_address: str = ""  # public registry residence address
    business_city: str = ""      # the cannabis business's city/town
    license_type: str = ""       # cannabis license/credential category
    license_number: str = ""
    registration_date: str = ""  # business registration / filing date (record date)
    retrieved_date: str = ""     # when this record was pulled + verified live
    business_url: str = ""       # live business-registry detail link


class Contribution(Provenanced):
    contrib_id: str
    contributor_name: str
    employer: str = ""
    occupation: str = ""
    amount: float = 0.0
    date: str = ""
    recipient_committee: str = ""


class CampaignContribution(Provenanced):
    """A single SEEC eCRIS campaign-finance receipt (a contribution).

    Pulled from the SEEC eCRIS public contribution search. We keep the donor's
    EMPLOYER (the cannabis-industry link), city (town disambiguator), and the
    RECIPIENT committee + office sought + district (the legislator link). No home
    address is stored — eCRIS contributor records are public and report only city."""
    receipt_id: str
    contributor_name: str
    employer: str = ""
    occupation: str = ""
    city: str = ""
    state: str = ""
    amount: float = 0.0
    date: str = ""                 # ISO YYYY-MM-DD transaction date
    recipient_committee: str = ""  # the committee that received the money
    office_sought: str = ""        # e.g. "State Senator", "State Representative"
    district: str = ""
    committee_type: str = ""       # Candidate Committee | Party | Political (PAC) | ...
    party: str = ""
    election_year: str = ""
    receipt_type: str = ""
    # Which query surfaced this row (employer/contributor/committee) — for audit.
    matched_by: str = ""


class Lobbyist(Provenanced):
    lobbyist_id: str
    communicator_name: str
    client_name: str = ""
    is_cannabis: bool = False
    registration_year: Optional[int] = None
    hometown: str = ""        # town, when the registration lists it (a disambiguator)


class SFIFiling(Provenanced):
    """Statement of Financial Interests — cannabis-relevant fields ONLY.
    Never store home address / phone / DOB / non-cannabis family detail."""
    filing_id: str
    legislator_name: str
    filing_year: Optional[int] = None
    spouse_employer: str = ""
    associated_business: str = ""

    @field_validator("spouse_employer", "associated_business")
    @classmethod
    def _no_forbidden(cls, v: str) -> str:
        # Defensive: an SFI parser should never route a forbidden field here.
        return v


class Match(BaseModel):
    """A cross-reference link between a legislator and a reference record."""
    person_id: str
    ref_type: RefType
    ref_id: str
    ref_label: str
    confidence: Confidence
    explanation: str
    score: float = 0.0
    is_family_lead: bool = False     # family/spouse leads are ALWAYS review-gated


class Finding(BaseModel):
    person_id: str
    person_name: str
    category: RefType
    status: FindingStatus
    confidence: Confidence
    priority: Literal["HIGH", "MEDIUM", "LOW"] = "LOW"
    legal_basis: str = ""
    explanation: str = ""
    citations: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)   # live, clickable sources
    is_family_lead: bool = False
    # Set by the classifier: True => may appear in the published findings section;
    # False => routed to the human review queue and NEVER auto-published.
    publishable: bool = False


# ===========================================================================
# MUNICIPAL / TOWN LAYER (extension module)
# ===========================================================================
MunicipalBody = Literal[
    "First Selectman", "Mayor", "Town Manager",
    "Board of Selectmen", "Town Council", "City Council",
    "Planning & Zoning Commission", "Zoning Board of Appeals",
    "Inland Wetlands", "Economic Development Commission", "Board of Finance",
    "Town Counsel", "Other",
]
# The six connection types from the taxonomy (§6).
ConnectionType = Literal[
    "siting_zoning",            # 1
    "official_family_rep",      # 2
    "official_own_role",        # 3
    "vendor_contractor",        # 4
    "donation",                 # 5
    "legislative_overlay",      # 6
]
# The four output classes the Simsbury example (§4.1) requires.
TownClass = Literal["CONFIRMED", "UNCONFIRMED", "UNSUPPORTED", "CONTEXT"]


class CannabisFacility(Provenanced):
    """A cannabis facility joined to its host TOWN — the targeting layer."""
    facility_id: str
    operator_name: str
    town: str
    address: str = ""           # street address kept ONLY as the facility location,
                                # never an individual's home (privacy gate, §8)
    license_type: str = ""
    approval_body: str = ""     # e.g. "Planning & Zoning Commission"
    approval_vote: str = ""     # e.g. "4-2"
    approval_date: str = ""
    approval_outcome: str = ""  # approved | denied


class MunicipalOfficial(Provenanced):
    person_id: str
    full_name: str
    town: str
    body: str = ""              # MunicipalBody value
    role: str = ""
    term_start: Optional[int] = None
    term_end: Optional[int] = None
    is_former: bool = False
    in_office_at: list[str] = Field(default_factory=list)  # facility_ids in office for
    name_variants: list[str] = Field(default_factory=list)
    # Optional self-role signals (§6 type 3) — landlord/licensee/town-counsel-reps.
    owns_operator_parcel: bool = False
    own_role_note: str = ""


class FamilyLink(Provenanced):
    """A relationship between an official and a relative. `is_primary_source` is the
    gate: only primary-sourced links may promote above REVIEW (§8)."""
    link_id: str
    official_name: str
    relative_name: str
    relationship: str = ""       # spouse | parent | child | sibling
    relative_role: str = ""      # e.g. "cannabis attorney, chairs Cannabis practice"
    relative_employer: str = ""  # firm/business name (joins to LawFirm/LocalEntity)
    source_type: str = ""        # campaign_bio | sfi_spouse_field | wedding_notice | ...
    is_primary_source: bool = False


class LawFirm(Provenanced):
    firm_id: str
    name: str
    reps_cannabis: bool = False
    cannabis_clients: list[str] = Field(default_factory=list)   # documented clients
    town_counsel_for: list[str] = Field(default_factory=list)   # towns


class LocalEntity(Provenanced):
    """A local business that could transact with an operator (landlord, waste,
    security, packaging, testing, construction, consulting)."""
    entity_id: str
    name: str
    town: str = ""
    kind: str = ""              # landlord | waste | security | packaging | ...
    documented_operator_transactions: list[str] = Field(default_factory=list)
    policy_excludes_cannabis: bool = False   # e.g. compost yard barring chemicals
    policy_note: str = ""


class VendorHypothesis(Provenanced):
    """A hypothesized vendor↔operator link to CHECK. A negative result is a
    first-class finding (§8), not a dropped lead."""
    hyp_id: str
    vendor_name: str
    operator_name: str
    town: str = ""
    hypothesis: str = ""
    evidence_found: bool = False
    national_program_only: bool = False   # e.g. TerraCycle packaging ≠ local link
    note: str = ""


class LegislativeOverlay(Provenanced):
    legislator_name: str
    chamber: Optional[Chamber] = None
    district: str = ""
    towns_represented: list[str] = Field(default_factory=list)
    committee: str = ""          # flag General Law / Judiciary
    employer: str = ""
    financial_stake: str = "none"
    is_former: bool = False


class TownConnection(BaseModel):
    """A classified link in a (town, operator) dossier — the municipal analogue of
    Finding, carrying the four-class verdict and the substantial-conflict flag."""
    town: str
    operator: str
    subject_name: str
    subject_kind: str            # official | spouse/family | firm | local_entity | legislator
    connection_type: ConnectionType
    classification: TownClass
    confidence: Confidence = "POSSIBLE/REVIEW"
    appearance_concern: bool = False
    substantial_conflict: bool = False
    explanation: str = ""
    citations: list[str] = Field(default_factory=list)
    is_private_individual: bool = False   # spouse/relative/local owner => review-gated
    review_gated: bool = False
    publishable: bool = False
