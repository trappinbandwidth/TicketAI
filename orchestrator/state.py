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

    # Extraction (Carver output)
    extraction: Optional[dict]
    extraction_2: Optional[dict]
    pass1_extraction: Optional[dict]
    pass2_extraction: Optional[dict]
    consensus_extraction: Optional[dict]
    dual_conflicts: list
    is_mock: bool
    token_usage: list  # per-Claude-call usage dicts, accumulated across document_gate/carver passes

    # Bolin output
    pass_status: Optional[str]
    low_confidence_fields: list
    referee_notes: Optional[str]

    # Charlotte Ray output
    cdl_point_impact: Optional[dict]

    # Banneker output
    jurisdiction_context: Optional[dict]

    # Madam Walker output
    attorney_matches: list
    no_attorney_flag: bool

    # Roux output
    intake_errors: list

    # Ida Wells output
    completeness_score: Optional[float]
    missing_fields: list

    # Jollof output
    driver_profile: Optional[dict]

    # Stagecoach Mary output
    mvr_request: Optional[dict]

    # Bass Reeves output
    psp_request: Optional[dict]

    # Tubman output
    urgency_level: Optional[str]
    urgency_reason: Optional[str]

    # Driver-submitted intake (Douglass inputs)
    driver_statement: Optional[dict]   # 9-field structured statement from driver form
    evidence_files: list               # [{url, caption, file_type, filename}]

    # Douglass output
    statement_of_record: Optional[dict]

    # Document Gate output
    doc_type: Optional[str]   # "photo" | "document" | "unknown"
    is_photo: Optional[bool]  # True when photo_analyst_node ran

    # Final
    final_result: Optional[dict]
    escalation_reason: Optional[str]
