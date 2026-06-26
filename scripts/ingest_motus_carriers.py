"""
Motus Carrier ingestion — FMCSA carrier authority data.

Supports two sources (in priority order):
  1. Local CSV  — pass path as first argument, or drop into Downloads
     e.g.  python3 scripts/ingest_motus_carriers.py /path/to/Carrier_-_All_With_History.csv
  2. Socrata API — data.transportation.gov dataset inys-ebih (fallback, ~59K records)

The local "All With History" CSV is the full authoritative source (~1.86M rows,
one row per docket/authority combination). Multiple rows share the same DOT_NUMBER.
This script deduplicates by DOT, preferring Active status.

Output:
    data/motus_carriers.json    — {usdot_number: carrier_dict}
    data/motus_suspended.json   — sorted list of inactive/revoked usdot_numbers

Usage:
    python3 scripts/ingest_motus_carriers.py
    python3 scripts/ingest_motus_carriers.py /Users/.../Carrier_-_All_With_History.csv
"""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Auth status codes (CSV schema) ────────────────────────────────────────────
# COMMON_STAT / CONTRACT_STAT / BROKER_STAT: A=Active  I=Inactive  N=Not held
ACTIVE_CODE    = "A"
INACTIVE_CODE  = "I"

SUSPENDED_STATUSES = {"Inactive", "Revoked", "Pending Revocation"}

# Auth type labels for display
_AUTH_TYPE_MAP = {
    ("A", "N", "N"): "Common carrier",
    ("N", "A", "N"): "Contract carrier",
    ("N", "N", "A"): "Broker",
    ("A", "A", "N"): "Common + Contract carrier",
    ("A", "N", "A"): "Common carrier + Broker",
    ("N", "A", "A"): "Contract carrier + Broker",
    ("A", "A", "A"): "Common + Contract carrier + Broker",
}

# ── CSV ingestion ─────────────────────────────────────────────────────────────

def _resolve_status(common: str, contract: str, broker: str) -> str:
    """Derive a single human-readable status from the three authority columns."""
    statuses = {common, contract, broker} - {"N", ""}
    if ACTIVE_CODE in statuses:
        return "Active"
    if not statuses:
        return "No Authority"
    return "Inactive"


def _auth_type_label(common: str, contract: str, broker: str) -> str:
    key = (
        ACTIVE_CODE if common == ACTIVE_CODE else "N",
        ACTIVE_CODE if contract == ACTIVE_CODE else "N",
        ACTIVE_CODE if broker == ACTIVE_CODE else "N",
    )
    return _AUTH_TYPE_MAP.get(key, "Motor Carrier")


def ingest_csv(csv_path: Path) -> dict[str, dict]:
    """
    Read the full history CSV and deduplicate by DOT_NUMBER.
    For each DOT we keep:
      - Status = Active if ANY row for that DOT has an active authority
      - Name from the first row (usually most recent docket)
      - Location from the first row
    Returns {dot_number: carrier_dict}
    """
    try:
        import pandas as pd
    except ImportError:
        log.error("Missing dependency. Run: python3 -m pip install pandas")
        sys.exit(1)

    log.info("Reading %s …", csv_path)
    df = pd.read_csv(csv_path, low_memory=False, dtype=str)
    df = df.fillna("")
    log.info("Loaded %d rows × %d columns", len(df), len(df.columns))

    # Normalize column names to uppercase to be safe
    df.columns = [c.strip().upper() for c in df.columns]

    required = {"DOT_NUMBER", "COMMON_STAT", "CONTRACT_STAT", "BROKER_STAT", "LEGAL_NAME"}
    missing  = required - set(df.columns)
    if missing:
        log.error("Missing expected columns: %s  (found: %s)", missing, list(df.columns))
        sys.exit(1)

    # Mark rows that have ANY active authority
    df["_any_active"] = (
        (df["COMMON_STAT"]   == ACTIVE_CODE) |
        (df["CONTRACT_STAT"] == ACTIVE_CODE) |
        (df["BROKER_STAT"]   == ACTIVE_CODE)
    )

    # Flag revocation-pending
    rev_cols = [c for c in ["COMMON_REV_PEND", "CONTRACT_REV_PEND", "BROKER_REV_PEND"] if c in df.columns]
    if rev_cols:
        df["_rev_pending"] = df[rev_cols].apply(
            lambda row: any(v.strip().upper() == "Y" for v in row), axis=1
        )
    else:
        df["_rev_pending"] = False

    # Deduplicate: for each DOT, sort so Active rows come first, take first row
    df_sorted = df.sort_values(
        by=["DOT_NUMBER", "_any_active"],
        ascending=[True, False],
    )
    df_dedup = df_sorted.drop_duplicates(subset="DOT_NUMBER", keep="first").copy()
    log.info("Unique DOT numbers: %d", len(df_dedup))

    # For suspended check: a DOT is active if ANY of its rows is active
    active_dots = set(df.loc[df["_any_active"], "DOT_NUMBER"].unique())
    revoked_dots = set(df.loc[df["_rev_pending"], "DOT_NUMBER"].unique()) - active_dots

    index: dict[str, dict] = {}
    for _, row in df_dedup.iterrows():
        dot     = str(row["DOT_NUMBER"]).strip()
        common  = str(row.get("COMMON_STAT",   "")).strip()
        contract = str(row.get("CONTRACT_STAT", "")).strip()
        broker  = str(row.get("BROKER_STAT",   "")).strip()

        # Override status using our full-history active_dots set
        if dot in active_dots:
            status = "Active"
        elif dot in revoked_dots:
            status = "Revoked"
        else:
            status = _resolve_status(common, contract, broker)

        index[dot] = {
            "usdot_number": dot,
            "docket_number": str(row.get("DOCKET_NUMBER", "")).strip(),
            "legal_name":    str(row.get("LEGAL_NAME",   "")).strip(),
            "dba_name":      str(row.get("DBA_NAME",     "")).strip(),
            "status":        status,
            "auth_type":     _auth_type_label(common, contract, broker),
            "state":         str(row.get("BUS_STATE_CODE", "")).strip(),
            "city":          str(row.get("BUS_CITY",       "")).strip(),
            "zip":           str(row.get("BUS_ZIP_CODE",   "")).strip(),
            "phone":         str(row.get("BUS_TELNO",      "")).strip(),
            "min_coverage":  str(row.get("MIN_COV_AMOUNT", "")).strip(),
            "passenger":     str(row.get("PASSENGER_CHK",  "")).strip() == "Y",
            "hazmat":        str(row.get("HHG_CHK",        "")).strip() == "Y",
        }

    return index


# ── Socrata API fallback ──────────────────────────────────────────────────────

SOCRATA_BASE = "https://data.transportation.gov/resource/inys-ebih.json"
PAGE_SIZE    = 1000


def _fetch_page(offset: int, session: object) -> list[dict]:
    params = {"$limit": PAGE_SIZE, "$offset": offset, "$order": "usdot_number"}
    resp = session.get(SOCRATA_BASE, params=params, timeout=30)  # type: ignore[attr-defined]
    resp.raise_for_status()
    return resp.json()


def ingest_api() -> dict[str, dict]:
    try:
        import requests
    except ImportError:
        log.error("Missing dependency. Run: python3 -m pip install requests")
        sys.exit(1)

    session = requests.Session()
    all_records: list[dict] = []
    offset = 0
    log.info("Fetching from Socrata API (fallback) …")
    while True:
        page = _fetch_page(offset, session)
        if not page:
            break
        all_records.extend(page)
        log.info("  fetched %d (total: %d)", len(page), len(all_records))
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(0.4)

    index: dict[str, dict] = {}
    for r in all_records:
        dot    = str(r.get("usdot_number", "")).strip()
        status = (r.get("op_auth_status") or "").strip()
        if not dot:
            continue
        existing = index.get(dot)
        if existing and existing["status"] == "Active" and status != "Active":
            continue
        index[dot] = {
            "usdot_number": dot,
            "docket_number": r.get("docket_number", ""),
            "legal_name":    r.get("legal_name",    ""),
            "dba_name":      r.get("dba_name",      ""),
            "status":        status,
            "auth_type":     r.get("op_auth_type",  ""),
            "state":         r.get("bus_state_code", ""),
            "city":          r.get("bus_city",       ""),
            "zip":           r.get("bus_zip_code",   ""),
            "phone":         r.get("bus_telno",      ""),
            "min_coverage":  r.get("min_cov_amount", ""),
            "passenger":     False,
            "hazmat":        False,
        }
    return index


# ── Output ────────────────────────────────────────────────────────────────────

def build_suspended_set(index: dict[str, dict]) -> list[str]:
    return sorted(
        dot for dot, c in index.items()
        if c["status"] not in ("Active", "Pending", "No Authority")
    )


def write_outputs(index: dict, suspended: list[str], out_dir: Path) -> None:
    out_dir.mkdir(exist_ok=True)
    (out_dir / "motus_carriers.json").write_text(json.dumps(index, indent=2))
    log.info("Wrote motus_carriers.json  (%d carriers)", len(index))
    (out_dir / "motus_suspended.json").write_text(json.dumps(suspended, indent=2))
    log.info("Wrote motus_suspended.json  (%d suspended/revoked)", len(suspended))

    # Status summary
    statuses: dict[str, int] = {}
    for c in index.values():
        s = c["status"] or "Unknown"
        statuses[s] = statuses.get(s, 0) + 1

    print("\n── Carrier status summary ──────────────────────")
    for status, count in sorted(statuses.items(), key=lambda x: -x[1]):
        print(f"  {status:<30} {count:>8,}")
    print(f"  {'TOTAL':<30} {len(index):>8,}")
    print("────────────────────────────────────────────────\n")


# ── Entry point ───────────────────────────────────────────────────────────────

def _find_local_csv() -> Path | None:
    """Auto-detect the CSV in common locations."""
    candidates = [
        Path(p) for p in [
            "/Users/digitalmercenary/Downloads/Carrier_-_All_With_History_20260625.csv",
        ]
    ]
    # Also check for any matching file in Downloads
    downloads = Path.home() / "Downloads"
    if downloads.exists():
        candidates += sorted(downloads.glob("Carrier_-_All_With_History*.csv"), reverse=True)

    for p in candidates:
        if p.exists():
            return p
    return None


def main() -> None:
    out_dir = Path(__file__).parent.parent / "data"

    # Resolve source: CLI arg > auto-detect local CSV > API
    if len(sys.argv) > 1:
        csv_path = Path(sys.argv[1])
        if not csv_path.exists():
            log.error("File not found: %s", csv_path)
            sys.exit(1)
        index = ingest_csv(csv_path)
    else:
        local = _find_local_csv()
        if local:
            log.info("Found local CSV: %s", local)
            index = ingest_csv(local)
        else:
            log.info("No local CSV found — falling back to Socrata API")
            index = ingest_api()

    suspended = build_suspended_set(index)
    write_outputs(index, suspended, out_dir)
    log.info("Done. Carrier lookup ready.")


if __name__ == "__main__":
    main()
