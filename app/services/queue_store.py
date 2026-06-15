import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
DB_PATH = BASE_DIR / "data" / "queue.db"
TRAINING_DIR = BASE_DIR / "training_data"
TRAINING_FILE = TRAINING_DIR / "approved_tickets.jsonl"

EXTRACTED_FIELDS = [
    "Date_of_Ticket__c", "Violation_Description__c", "Violation_Category__c",
    "Court_Date__c", "Accident__c", "Drivers_License_Type__c", "Ticket_Court__c",
    "Court_Phone_Number__c", "Ticket_City__c", "Ticket_County__c", "Ticket_State__c",
    "Insp_Report_Num__c", "Citation_Number__c",
    "Inspection_Date__c", "Inspection_Time__c", "Inspection_State__c",
    "Inspection_County__c", "Inspection_City__c", "Inspection_Location__c",
    "DOT_Number__c", "Inspection_Level__c", "Driver_OOS__c", "Vehicle_OOS__c",
    "BASIC_Categories__c", "Crash_Report_Number__c", "Crash_Date__c",
    "Crash_State__c", "Crash_County__c", "Crash_City__c", "Crash_Location__c",
    "Federal_Recordable__c", "State_Reportable__c", "Number_of_Fatalities__c",
    "Number_of_Injuries__c", "Towaway__c", "Citation_Issued__c", "HM_Involved__c",
    "Civil_Penalty_Case_Number__c", "Civil_Penalty_Amount__c", "Civil_Penalty_Due_Date__c",
    "BASIC_Category__c", "CDL_License_Number__c", "CDL_State__c", "CDL_Class__c",
    "CDL_Expiration__c", "CDL_Endorsements__c", "CDL_Restrictions__c",
    "Driver_First_Name__c", "Driver_Last_Name__c", "Driver_DOB__c",
    "MVR_License_Number__c", "MVR_State__c", "MVR_Class__c", "MVR_Generated_Date__c",
    "MVR_Violations_Summary__c", "MVR_Total_Points__c", "MVR_Suspension_Count__c",
]


_SEED_ATTORNEYS = [
    # Florida
    ("mock-fl-001", "James R. Holloway",   "jholloway@hollowaytransportlaw.com", "(850) 555-0142", "Florida", "", 4.8, 0.74, 312),
    ("mock-fl-002", "Sandra M. Vega",      "svega@vegacdldefense.com",           "(407) 555-0219", "Florida", "", 4.6, 0.68, 187),
    ("mock-fl-003", "Derek W. Fontaine",   "dfontaine@fontainelegal.com",        "(305) 555-0387", "Florida", "", 4.5, 0.61,  98),
    # Maryland
    ("mock-md-001", "Patricia L. Nguyen",  "pnguyen@nguyen-trucklaw.com",        "(410) 555-0174", "Maryland", "", 4.9, 0.81, 445),
    ("mock-md-002", "Thomas A. Griggs",    "tgriggs@griggslawmd.com",            "(301) 555-0263", "Maryland", "", 4.7, 0.72, 229),
    ("mock-md-003", "Carol B. Simmons",    "csimmons@simmonstraffic.com",        "(443) 555-0318", "Maryland", "", 4.4, 0.65, 153),
    # Washington
    ("mock-wa-001", "Marcus J. Breckenridge", "mbreckenridge@breckenridgecdl.com", "(206) 555-0492", "Washington", "", 4.7, 0.77, 381),
    ("mock-wa-002", "Yuki T. Yamamoto",    "yyamamoto@yamamotolegal.com",        "(253) 555-0135", "Washington", "", 4.6, 0.71, 204),
    ("mock-wa-003", "Brenda K. Okafor",    "bokafor@okafortrucklaw.com",         "(360) 555-0277", "Washington", "", 4.3, 0.58, 117),
    ("mock-wa-004", "Kevin L. Sorensen",   "ksorensen@sorensentraffic.com",      "(509) 555-0348", "Washington", "", 4.5, 0.69, 278),
    ("mock-wa-005", "Alicia R. Montoya",   "amontoya@montoyacdllaw.com",         "(425) 555-0461", "Washington", "", 4.8, 0.83, 512),
]


def init_db() -> None:
    os.makedirs(DB_PATH.parent, exist_ok=True)
    os.makedirs(TRAINING_DIR, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS queue (
                id                        TEXT PRIMARY KEY,
                filename                  TEXT NOT NULL,
                pass_status               TEXT NOT NULL,
                status                    TEXT NOT NULL DEFAULT 'pending',
                created_at                TEXT NOT NULL,
                updated_at                TEXT NOT NULL,
                image_b64                 TEXT,
                process_response_json     TEXT NOT NULL,
                reject_reason             TEXT,
                edited_fields_json        TEXT,
                pass1_extraction_json     TEXT,
                pass2_extraction_json     TEXT,
                consensus_extraction_json TEXT,
                doc_type                  TEXT,
                prompt_version            TEXT,
                attorney_matched          INTEGER DEFAULT 0,
                attorney_match_type       TEXT,
                has_price_estimate        INTEGER DEFAULT 0,
                price_estimate_json       TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id     TEXT NOT NULL,
                agent       TEXT NOT NULL,
                event       TEXT NOT NULL,
                detail_json TEXT,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (scan_id) REFERENCES queue(id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_events_scan   ON agent_events(scan_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_events_agent  ON agent_events(agent)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_created       ON queue(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_status        ON queue(status)")

        # Attorneys table — local replacement for Salesforce attorney records
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attorneys (
                id            TEXT PRIMARY KEY,
                name          TEXT NOT NULL,
                email         TEXT,
                phone         TEXT,
                state         TEXT NOT NULL,
                county        TEXT NOT NULL DEFAULT '',
                rating        REAL,
                win_rate      REAL NOT NULL DEFAULT 0.0,
                total_tickets INTEGER NOT NULL DEFAULT 0,
                active        INTEGER NOT NULL DEFAULT 1,
                notes         TEXT,
                created_at    TEXT NOT NULL,
                updated_at    TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_attorneys_state ON attorneys(state)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_attorneys_state_county ON attorneys(state, county)")

        # Seed default attorneys if table is empty
        count = conn.execute("SELECT COUNT(*) FROM attorneys").fetchone()[0]
        if count == 0:
            ts = _now()
            conn.executemany(
                """INSERT OR IGNORE INTO attorneys
                   (id, name, email, phone, state, county, rating, win_rate, total_tickets, active, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,1,?,?)""",
                [(a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8], ts, ts) for a in _SEED_ATTORNEYS],
            )

        # Non-destructive migration for existing databases
        existing = {r[1] for r in conn.execute("PRAGMA table_info(queue)").fetchall()}
        for col, typedef in [
            ("pass1_extraction_json",     "TEXT"),
            ("pass2_extraction_json",     "TEXT"),
            ("consensus_extraction_json", "TEXT"),
            ("doc_type",                  "TEXT"),
            ("prompt_version",            "TEXT"),
            ("attorney_matched",          "INTEGER DEFAULT 0"),
            ("attorney_match_type",       "TEXT"),
            ("has_price_estimate",        "INTEGER DEFAULT 0"),
            ("price_estimate_json",       "TEXT"),
        ]:
            if col not in existing:
                conn.execute(f"ALTER TABLE queue ADD COLUMN {col} {typedef}")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_doc_type ON queue(doc_type)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_agent_event(scan_id: str, agent: str, event: str, detail: dict | None = None) -> None:
    """Write a structured event for one agent step. Safe to call even if scan not yet committed."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO agent_events (scan_id, agent, event, detail_json, created_at) VALUES (?,?,?,?,?)",
                (scan_id, agent, event, json.dumps(detail) if detail else None, _now()),
            )
    except Exception:
        pass  # Never crash the pipeline over a logging failure


def save_scan(
    id: str,
    filename: str,
    pass_status: str,
    image_b64: str,
    process_response_json: str,
    pass1_extraction: dict | None = None,
    pass2_extraction: dict | None = None,
    consensus_extraction: dict | None = None,
    doc_type: str | None = None,
    prompt_version: str | None = None,
    attorney_matched: bool = False,
    attorney_match_type: str | None = None,
    has_price_estimate: bool = False,
    price_estimate: dict | None = None,
) -> None:
    ts = _now()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """INSERT INTO queue (
                id, filename, pass_status, status, created_at, updated_at,
                image_b64, process_response_json,
                pass1_extraction_json, pass2_extraction_json, consensus_extraction_json,
                doc_type, prompt_version,
                attorney_matched, attorney_match_type,
                has_price_estimate, price_estimate_json
            ) VALUES (?,?,?,  'pending',?,?,  ?,?,  ?,?,?,  ?,?,  ?,?,  ?,?)""",
            (
                id, filename, pass_status, ts, ts,
                image_b64, process_response_json,
                json.dumps(pass1_extraction) if pass1_extraction else None,
                json.dumps(pass2_extraction) if pass2_extraction else None,
                json.dumps(consensus_extraction) if consensus_extraction else None,
                doc_type, prompt_version,
                int(attorney_matched), attorney_match_type,
                int(has_price_estimate), json.dumps(price_estimate) if price_estimate else None,
            ),
        )


def list_recent(limit: int = 50) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT id, filename, pass_status, status, created_at, updated_at,
               doc_type, prompt_version,
               attorney_matched, attorney_match_type, has_price_estimate
               FROM queue ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_item(id: str) -> dict | None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM queue WHERE id = ?", (id,)).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["process_response"] = json.loads(item["process_response_json"])
    item["edited_fields"] = json.loads(item["edited_fields_json"]) if item["edited_fields_json"] else {}
    item["pass1_extraction"] = json.loads(item["pass1_extraction_json"]) if item["pass1_extraction_json"] else {}
    item["pass2_extraction"] = json.loads(item["pass2_extraction_json"]) if item["pass2_extraction_json"] else {}
    item["consensus_extraction"] = json.loads(item["consensus_extraction_json"]) if item["consensus_extraction_json"] else {}
    return item


def get_agent_events(scan_id: str) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM agent_events WHERE scan_id=? ORDER BY created_at ASC",
            (scan_id,),
        ).fetchall()
    result = []
    for r in rows:
        row = dict(r)
        row["detail"] = json.loads(row["detail_json"]) if row["detail_json"] else {}
        result.append(row)
    return result


def approve_item(id: str, edited_fields: dict) -> None:
    item = get_item(id)
    if item is None:
        raise ValueError(f"Queue item not found: {id}")

    ts = _now()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE queue SET status='approved', updated_at=?, edited_fields_json=? WHERE id=?",
            (ts, json.dumps(edited_fields), id),
        )

    process_response = item["process_response"]
    original = process_response.get("result", {})

    final_values = {}
    for field in EXTRACTED_FIELDS:
        if field in edited_fields:
            final_values[field] = edited_fields[field]
        elif field in original and isinstance(original[field], dict):
            final_values[field] = original[field].get("value", "")
        else:
            final_values[field] = ""

    was_edited = any(
        final_values.get(f) != (original.get(f, {}) or {}).get("value", "")
        for f in EXTRACTED_FIELDS
        if f in edited_fields
    )

    # Per-field feedback from ✓/✗ buttons (stored in edited_fields as __feedback__ key)
    field_feedback = edited_fields.pop("__feedback__", {})

    record = {
        "id": id,
        "filename": item["filename"],
        "approved_at": ts,
        "pass_status": item["pass_status"],
        "doc_type": item.get("doc_type"),
        "prompt_version": item.get("prompt_version"),
        "original_extraction": original,
        "pass1_extraction": item.get("pass1_extraction", {}),
        "pass2_extraction": item.get("pass2_extraction", {}),
        "consensus_extraction": item.get("consensus_extraction", {}),
        "final_values": final_values,
        "was_edited": was_edited,
        "field_feedback": field_feedback,  # {"Court_Date__c": "correct", "Violation_Description__c": "wrong"}
    }

    with open(TRAINING_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def reject_item(id: str, reason: str) -> None:
    ts = _now()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE queue SET status='rejected', updated_at=?, reject_reason=? WHERE id=?",
            (ts, reason, id),
        )


def list_approved() -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM queue WHERE status='approved' ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]
