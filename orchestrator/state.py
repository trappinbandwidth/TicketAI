from typing import Any, Optional
from typing_extensions import TypedDict


class PassStatus:
    GREEN = "green"   # High confidence — zero human intervention
    YELLOW = "yellow" # Medium confidence — consensus loop
    RED = "red"       # Low confidence — human escalation required


class TicketState(TypedDict):
    # Input
    images_b64: list[str]
    ocr_text: str
    driver_name: Optional[str]
    driver_id: Optional[str]
    ticket_id: Optional[str]
    filename: str
    prompt_version: str
    scan_id: str
    word_positions: list

    # Extraction (Lone Ranger output)
    extraction: Optional[dict]
    extraction_2: Optional[dict]
    pass1_extraction: Optional[dict]
    pass2_extraction: Optional[dict]
    consensus_extraction: Optional[dict]
    dual_conflicts: list
    is_mock: bool

    # Referee output
    pass_status: Optional[str]
    low_confidence_fields: list
    referee_notes: Optional[str]

    # Book Worm output
    cdl_point_impact: Optional[dict]

    # Research Ron output
    jurisdiction_context: Optional[dict]

    # Team Quest output
    attorney_matches: list
    no_attorney_flag: bool

    # Case Intake output
    intake_errors: list

    # Document Completeness output
    completeness_score: Optional[float]
    missing_fields: list

    # PII Match output
    driver_profile: Optional[dict]

    # MVR Request output
    mvr_request: Optional[dict]

    # PSP Request output
    psp_request: Optional[dict]

    # Urgency Router output
    urgency_level: Optional[str]
    urgency_reason: Optional[str]

    # Driver-submitted intake (Statement of Record inputs)
    driver_statement: Optional[dict]   # 9-field structured statement from driver form
    evidence_files: list               # [{url, caption, file_type, filename}]

    # Statement of Record output
    statement_of_record: Optional[dict]

    # Final
    final_result: Optional[dict]
    escalation_reason: Optional[str]
