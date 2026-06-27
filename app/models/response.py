from pydantic import BaseModel
from typing import Any, Optional


class PriceEstimate(BaseModel):
    avg_attny_price: float
    cdl_fee: int
    driver_price_base: int
    driver_price_low: int
    driver_price_high: int
    win_rate_pct: float
    sample_size: int
    high_risk: bool
    data_source: str   # "historical" | "fallback" | "unavailable"
    display: str       # "$765 – $1,080"
    note: str = ""


class BoundingBox(BaseModel):
    x: float       # left edge, 0–1 fraction of page width
    y: float       # top edge, 0–1 fraction of page height
    w: float       # width, 0–1
    h: float       # height, 0–1
    page: int = 1  # 1-indexed page number


class ExtractedField(BaseModel):
    value: str
    confidence_score: float
    ai_reason: str
    bbox: Optional[BoundingBox] = None
    items: Optional[list[str]] = None       # populated when value contains multiple violations
    raw_evidence: Optional[str] = None      # verbatim OCR snippet used for extraction


class FileTypeAnalysis(BaseModel):
    confidence_score: float
    ai_reason: str


class CdlPointImpact(BaseModel):
    violation_category: str
    cdl_points: int
    severity: str
    csa_category: str
    must_appear_in_court: bool
    attorney_recommended: bool


class DocSeverityScore(BaseModel):
    """Generic severity score for all non-ticket document types."""
    doc_type: str
    severity: str           # LOW | MEDIUM | HIGH | CRITICAL
    severity_score: int     # 0–100
    key_factors: list[str]
    attorney_recommended: bool
    action_required: str
    days_to_respond: Optional[int] = None


class DocumentResult(BaseModel):
    """
    Universal extraction result covering all 7 document types.
    Ticket fields are always present (empty string when not applicable).
    Type-specific fields are Optional and populated only when relevant.
    """
    file_type: str          # Ticket | Inspection Report | Warning | Crash Report | Civil Penalty | CDL | MVR
    other_document_types: list[str]
    file_type_analysis: FileTypeAnalysis
    file_name: str
    document_text_format: str

    # ── Ticket / Warning fields (always present in JSON) ──────────────────
    Date_of_Ticket__c: ExtractedField
    Violation_Description__c: ExtractedField
    Violation_Category__c: ExtractedField
    Court_Date__c: ExtractedField
    Accident__c: ExtractedField
    Drivers_License_Type__c: ExtractedField
    Ticket_Court__c: ExtractedField
    Court_Phone_Number__c: ExtractedField
    Ticket_City__c: ExtractedField
    Ticket_County__c: ExtractedField
    Ticket_State__c: ExtractedField
    Insp_Report_Num__c: ExtractedField
    Citation_Number__c: ExtractedField

    # ── Ticket defense / economic fields (Tier 1) ────────────────────────
    Fine_Amount__c: Optional[ExtractedField] = None            # base fine / bail / bond dollar amount
    Penalty_Amount__c: Optional[ExtractedField] = None         # separate penalty/surcharge if listed distinctly
    Fine_Printed_On_Ticket__c: Optional[ExtractedField] = None # "Yes" | "No" — builds state knowledge DB
    Statute_Code__c: Optional[ExtractedField] = None           # violation statute/ordinance code
    Mandatory_Appearance__c: Optional[ExtractedField] = None   # "Yes" | "No"
    School_Zone__c: Optional[ExtractedField] = None            # "Yes" | "No"
    Construction_Zone__c: Optional[ExtractedField] = None      # "Yes" | "No"

    # ── Ticket defense fields (Tier 2) ────────────────────────────────────
    Officer_Name__c: Optional[ExtractedField] = None           # issuing officer name
    Officer_Badge__c: Optional[ExtractedField] = None          # badge / ID number
    Speed_Enforcement_Method__c: Optional[ExtractedField] = None  # Radar | LIDAR | Pacing | Aircraft | Visual | VASCAR | Photo
    Vehicle_Plate__c: Optional[ExtractedField] = None          # license plate number on ticket
    Vehicle_State__c: Optional[ExtractedField] = None          # plate issuing state

    # ── Inspection Report fields ──────────────────────────────────────────
    Inspection_Date__c: Optional[ExtractedField] = None
    Inspection_Time__c: Optional[ExtractedField] = None        # HH:MM AM/PM or 24h start time
    Inspection_State__c: Optional[ExtractedField] = None
    Inspection_County__c: Optional[ExtractedField] = None
    Inspection_City__c: Optional[ExtractedField] = None        # city or nearest city
    Inspection_Location__c: Optional[ExtractedField] = None    # highway, milepost, street address
    DOT_Number__c: Optional[ExtractedField] = None
    Inspection_Level__c: Optional[ExtractedField] = None       # I | II | III | IV | V | VI
    VIN__c: Optional[ExtractedField] = None
    Unit_Make__c: Optional[ExtractedField] = None
    Unit_License_Plate__c: Optional[ExtractedField] = None
    Driver_OOS__c: Optional[ExtractedField] = None             # Yes | No
    Vehicle_OOS__c: Optional[ExtractedField] = None            # Yes | No
    BASIC_Categories__c: Optional[ExtractedField] = None       # comma-separated BASIC categories

    # ── Crash Report fields ───────────────────────────────────────────────
    Crash_Report_Number__c: Optional[ExtractedField] = None
    Crash_Date__c: Optional[ExtractedField] = None
    Crash_State__c: Optional[ExtractedField] = None
    Crash_County__c: Optional[ExtractedField] = None
    Crash_City__c: Optional[ExtractedField] = None
    Crash_Location__c: Optional[ExtractedField] = None
    Federal_Recordable__c: Optional[ExtractedField] = None     # Yes | No
    State_Reportable__c: Optional[ExtractedField] = None       # Yes | No
    Number_of_Fatalities__c: Optional[ExtractedField] = None
    Number_of_Injuries__c: Optional[ExtractedField] = None
    Towaway__c: Optional[ExtractedField] = None                # Yes | No
    Citation_Issued__c: Optional[ExtractedField] = None        # Yes | No
    HM_Involved__c: Optional[ExtractedField] = None            # Yes | No

    # ── Civil Penalty fields ──────────────────────────────────────────────
    Civil_Penalty_Case_Number__c: Optional[ExtractedField] = None
    Civil_Penalty_Amount__c: Optional[ExtractedField] = None   # dollar amount as string
    Civil_Penalty_Due_Date__c: Optional[ExtractedField] = None
    BASIC_Category__c: Optional[ExtractedField] = None

    # ── CDL License fields ────────────────────────────────────────────────
    CDL_License_Number__c: Optional[ExtractedField] = None
    CDL_State__c: Optional[ExtractedField] = None
    CDL_Class__c: Optional[ExtractedField] = None              # A | B | C
    CDL_Expiration__c: Optional[ExtractedField] = None
    CDL_Endorsements__c: Optional[ExtractedField] = None       # H, N, P, S, T, X
    CDL_Restrictions__c: Optional[ExtractedField] = None
    Driver_First_Name__c: Optional[ExtractedField] = None
    Driver_Last_Name__c: Optional[ExtractedField] = None
    Driver_DOB__c: Optional[ExtractedField] = None
    Driver_Address__c: Optional[ExtractedField] = None

    # ── MVR fields ────────────────────────────────────────────────────────
    MVR_License_Number__c: Optional[ExtractedField] = None
    MVR_State__c: Optional[ExtractedField] = None
    MVR_Class__c: Optional[ExtractedField] = None
    MVR_Generated_Date__c: Optional[ExtractedField] = None
    MVR_Violations_Summary__c: Optional[ExtractedField] = None  # text summary of violations
    MVR_Total_Points__c: Optional[ExtractedField] = None
    MVR_Suspension_Count__c: Optional[ExtractedField] = None


# Backward-compatible alias
TicketResponse = DocumentResult


class CdlPointEstimate(BaseModel):
    """CDL point impact estimate by state and violation — for attorney and driver reference."""
    violation_category: str
    state: str
    state_points_min: int
    state_points_max: int
    state_points_display: str           # "3–6 pts"
    federal_serious_violation: bool     # counts toward 60/120-day CDL disqualification under 49 CFR 383.51
    federal_major_violation: bool       # triggers 1-year+ CDL disqualification under 49 CFR 383.51
    disqualification_risk: str          # None | Low | Medium | High | Immediate
    disqualification_note: str          # plain-English consequence
    csa_severity_weight: int            # FMCSA CSA severity weight 1–10
    insurance_impact: str               # Minimal | Moderate | Significant | Severe
    school_zone_applied: bool
    construction_zone_applied: bool
    zone_points_added: int              # extra points from zone modifier
    data_source: str                    # "state_schedule" | "estimate"


class PaymentOption(BaseModel):
    plan: str               # "Pay in Full" | "2 Payments" | "3 Payments" | "4 Payments"
    installments: int
    down_payment: float
    monthly_payment: float
    total: float
    available: bool


class PaymentOptions(BaseModel):
    base_amount: float
    currency: str = "USD"
    days_until_court: Optional[int] = None
    options: list[PaymentOption]
    note: str = ""


class CountyCourt(BaseModel):
    county: str
    court_name: str
    website: str
    scheduling_url: str
    phone: str
    address: str
    notes: str = ""


class CourtInfo(BaseModel):
    state: str
    state_name: str
    court_system: str
    state_portal: str
    online_payment_url: str
    scheduling_url: str
    cdl_info_url: str
    appear_required_for_serious: bool
    appear_required: bool
    notes: str = ""
    county_court: Optional[CountyCourt] = None


class AttorneyMatch(BaseModel):
    attorney_id: str
    name: str
    email: str
    phone: str
    rating: Optional[float]
    win_rate: float
    total_tickets: int
    match_type: str      # "county" | "state"


class ProcessResponse(BaseModel):
    success: bool
    mock: bool
    filename: str
    pages_processed: int

    # Referee / orchestration outputs
    pass_status: str                          # green | yellow | red
    low_confidence_fields: list[str]
    referee_notes: Optional[str]
    cdl_point_impact: Optional[CdlPointImpact]
    doc_severity: Optional[DocSeverityScore] = None
    escalation_reason: Optional[str]

    queue_id: Optional[str] = None
    price_estimate: Optional[PriceEstimate] = None
    dual_conflicts: list[str] = []
    attorney_matches: list[AttorneyMatch] = []
    no_attorney_flag: bool = False

    cached: bool = False
    artificial_court_date: bool = False
    court_info: Optional[CourtInfo] = None
    cdl_point_estimate: Optional[CdlPointEstimate] = None
    payment_options: Optional[PaymentOptions] = None

    # New agent outputs
    urgency_level: Optional[str] = None
    urgency_reason: Optional[str] = None
    completeness_score: Optional[float] = None
    missing_fields: list[str] = []

    result: DocumentResult
