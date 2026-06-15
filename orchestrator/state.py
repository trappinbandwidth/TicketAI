from typing import Any
from typing_extensions import TypedDict


class PassStatus:
    GREEN = "green"   # High confidence — zero human intervention
    YELLOW = "yellow" # Medium confidence — consensus loop
    RED = "red"       # Low confidence — human escalation required


class TicketState(TypedDict):
    # Input
    images_b64: list[str]
    ocr_text: str
    driver_name: str | None
    filename: str
    prompt_version: str
    scan_id: str           # UUID assigned at intake — used for agent event logging
    word_positions: list   # WordPosition objects from Textract (empty list if unavailable)

    # Extraction (Lone Ranger output)
    extraction: dict[str, Any] | None
    extraction_2: dict[str, Any] | None   # second pass (non-green only)
    pass1_extraction: dict[str, Any] | None   # stored for dashboard analytics
    pass2_extraction: dict[str, Any] | None   # stored for dashboard analytics
    consensus_extraction: dict[str, Any] | None  # stored for dashboard analytics
    dual_conflicts: list[str]             # fields where both passes disagreed confidently
    is_mock: bool

    # Referee output
    pass_status: str | None          # green | yellow | red
    low_confidence_fields: list[str] # fields below threshold
    referee_notes: str | None

    # Book Worm output
    cdl_point_impact: dict[str, Any] | None

    # Final
    final_result: dict[str, Any] | None
    escalation_reason: str | None
