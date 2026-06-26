"""
FMCSA Crash File ingestion.
Builds two lookup indexes from the FMCSA crash records CSV:

  1. data/crash_by_dot.json  — crash history per carrier (DOT#)
  2. data/crash_by_state.json — aggregate crash stats per state (for Research Ron)

Usage:
    python3 scripts/ingest_crash_data.py
    python3 scripts/ingest_crash_data.py /path/to/Crash_File.csv

Key columns used:
    DOT_NUMBER, REPORT_STATE, REPORT_DATE, FATALITIES, INJURIES,
    TOW_AWAY, FEDERAL_RECORDABLE, STATE_RECORDABLE, TRUCK_BUS_IND,
    HAZMAT_RELEASED, CRASH_CARRIER_NAME, CRASH_CARRIER_STATE
"""
from __future__ import annotations

import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Only read the columns we actually need — keeps memory low on large files
_USECOLS = [
    "DOT_NUMBER", "REPORT_STATE", "REPORT_DATE",
    "FATALITIES", "INJURIES", "TOW_AWAY",
    "FEDERAL_RECORDABLE", "STATE_RECORDABLE",
    "TRUCK_BUS_IND", "HAZMAT_RELEASED",
    "CRASH_CARRIER_NAME", "CRASH_CARRIER_STATE",
]

# Minimum year to include (crashes before 2000 have poor data quality)
MIN_YEAR = 2000


def _safe_int(v: object, default: int = 0) -> int:
    try:
        return int(float(str(v)))
    except (ValueError, TypeError):
        return default


def _extract_year(date_val: object) -> int | None:
    """REPORT_DATE is stored as YYYYMMDD integer."""
    s = str(date_val).strip()
    if len(s) >= 4 and s[:4].isdigit():
        return int(s[:4])
    return None


CHUNK_SIZE = 100_000  # rows per chunk — keeps RAM under ~500MB


def ingest(csv_path: Path) -> tuple[dict, dict]:
    """
    Chunked read — never loads more than CHUNK_SIZE rows at once.
    Aggregates incrementally into plain dicts to stay memory-efficient.

    Returns:
      dot_index   — {dot_number: {crash_count, fatal_count, ...}}
      state_index — {state: {crash_count, fatal_count, ...}}
    """
    try:
        import pandas as pd
    except ImportError:
        log.error("Missing dependency. Run: python3 -m pip install pandas")
        sys.exit(1)

    available = pd.read_csv(csv_path, nrows=0).columns.tolist()
    usecols   = [c for c in _USECOLS if c in available]
    missing   = set(_USECOLS) - set(usecols)
    if missing:
        log.warning("Columns not found (will be skipped): %s", missing)

    dot_index:   dict[str, dict] = {}
    state_index: dict[str, dict] = {}
    total_rows = kept = chunk_num = 0

    log.info("Reading %s in chunks of %d …", csv_path, CHUNK_SIZE)

    reader = pd.read_csv(
        csv_path, usecols=usecols, low_memory=False,
        chunksize=CHUNK_SIZE, dtype=str,
    )

    for chunk in reader:
        chunk_num += 1
        total_rows += len(chunk)
        if chunk_num % 10 == 0:
            log.info("  … processed %d rows, kept %d", total_rows, kept)

        # Filter truck/bus
        if "TRUCK_BUS_IND" in chunk.columns:
            chunk = chunk[chunk["TRUCK_BUS_IND"].isin(["T", "B"])]
        if chunk.empty:
            continue

        # Year filter
        if "REPORT_DATE" in chunk.columns:
            years = pd.to_numeric(
                chunk["REPORT_DATE"].str[:4], errors="coerce"
            ).fillna(0).astype(int)
            chunk = chunk[years >= MIN_YEAR]
            chunk = chunk.copy()
            chunk["_year"] = years[chunk.index]
        else:
            chunk["_year"] = 0

        if chunk.empty:
            continue
        kept += len(chunk)

        # Coerce
        for col in ["FATALITIES", "INJURIES"]:
            chunk[col] = pd.to_numeric(chunk.get(col, 0), errors="coerce").fillna(0).astype(int)
        for col in ["FEDERAL_RECORDABLE", "TOW_AWAY", "HAZMAT_RELEASED"]:
            chunk[col] = (chunk.get(col, "").astype(str).str.upper() == "Y").astype(int)

        chunk["DOT_NUMBER"]   = chunk.get("DOT_NUMBER",   "").astype(str).str.strip()
        chunk["REPORT_STATE"] = chunk.get("REPORT_STATE", "").astype(str).str.strip().str.upper()

        chunk = chunk[~chunk["DOT_NUMBER"].isin(["", "0", "nan", "NaN"])]

        # ── Accumulate state totals ──────────────────────────────────────────
        for state, grp in chunk.groupby("REPORT_STATE"):
            if not state:
                continue
            s = state_index.setdefault(state, {
                "crash_count": 0, "fatal_count": 0, "injury_count": 0,
                "truck_count": 0, "federal_recordable": 0, "tow_away": 0, "hazmat": 0,
            })
            s["crash_count"]        += len(grp)
            s["truck_count"]        += len(grp)
            s["fatal_count"]        += int(grp["FATALITIES"].sum())
            s["injury_count"]       += int(grp["INJURIES"].sum())
            s["federal_recordable"] += int(grp["FEDERAL_RECORDABLE"].sum())
            s["tow_away"]           += int(grp["TOW_AWAY"].sum())
            s["hazmat"]             += int(grp["HAZMAT_RELEASED"].sum())

        # ── Accumulate DOT totals ────────────────────────────────────────────
        for dot, grp in chunk.groupby("DOT_NUMBER"):
            d = dot_index.setdefault(str(dot), {
                "crash_count": 0, "fatal_count": 0, "injury_count": 0,
                "federal_recordable": 0, "tow_away": 0, "hazmat": 0,
                "states": set(), "years": set(), "carrier_name": "",
            })
            d["crash_count"]        += len(grp)
            d["fatal_count"]        += int(grp["FATALITIES"].sum())
            d["injury_count"]       += int(grp["INJURIES"].sum())
            d["federal_recordable"] += int(grp["FEDERAL_RECORDABLE"].sum())
            d["tow_away"]           += int(grp["TOW_AWAY"].sum())
            d["hazmat"]             += int(grp["HAZMAT_RELEASED"].sum())
            d["states"].update(grp["REPORT_STATE"].dropna().unique().tolist())
            d["years"].update(grp["_year"][grp["_year"] > 0].unique().tolist())
            if not d["carrier_name"] and "CRASH_CARRIER_NAME" in grp.columns:
                name = grp["CRASH_CARRIER_NAME"].dropna().astype(str).str.strip()
                name = name[name != ""]
                if not name.empty:
                    d["carrier_name"] = name.iloc[0]

    log.info("Total rows: %d  |  Kept (truck/bus, year>=%d): %d", total_rows, MIN_YEAR, kept)

    # Serialize sets → sorted lists
    for dot, d in dot_index.items():
        years  = sorted(d["years"])
        states = sorted(d["states"])
        d["states"]           = states
        d["years"]            = years
        d["most_recent_year"] = max(years) if years else None

    log.info("DOT index: %d carriers with crash history", len(dot_index))
    return dot_index, state_index


def write_outputs(dot_index: dict, state_index: dict, out_dir: Path) -> None:
    out_dir.mkdir(exist_ok=True)

    dot_path   = out_dir / "crash_by_dot.json"
    state_path = out_dir / "crash_by_state.json"

    dot_path.write_text(json.dumps(dot_index, indent=2))
    log.info("Wrote %s  (%d carriers with crash history)", dot_path, len(dot_index))

    state_path.write_text(json.dumps(state_index, indent=2))
    log.info("Wrote %s  (%d states)", state_path, len(state_index))

    # Top states by crash count
    print("\n── Crashes by state (top 15, since 2000) ─────────────────────")
    print(f"  {'State':<6}  {'Crashes':>8}  {'Fatalities':>10}  {'Fed Recordable':>14}  {'Hazmat':>6}")
    print("  " + "─" * 52)
    top_states = sorted(state_index.items(), key=lambda x: -x[1]["crash_count"])[:15]
    for state, s in top_states:
        print(
            f"  {state:<6}  {s['crash_count']:>8,}  {s['fatal_count']:>10,}"
            f"  {s['federal_recordable']:>14,}  {s['hazmat']:>6,}"
        )

    total_crashes = sum(s["crash_count"] for s in state_index.values())
    total_fatal   = sum(s["fatal_count"]  for s in state_index.values())
    print(f"\n  Total crashes (≥{MIN_YEAR}): {total_crashes:,}  |  Fatalities: {total_fatal:,}")

    # Carriers with worst crash history
    print("\n── Top 10 carriers by crash count ────────────────────────────")
    top_dot = sorted(dot_index.items(), key=lambda x: -x[1]["crash_count"])[:10]
    for dot, d in top_dot:
        name = d["carrier_name"][:30] or f"DOT#{dot}"
        print(f"  {name:<32} crashes={d['crash_count']:>5}  fatal={d['fatal_count']:>4}  DOT#{dot}")
    print()


def _find_csv() -> Path | None:
    downloads = Path.home() / "Downloads"
    candidates = sorted(downloads.glob("Crash_File*.csv"), reverse=True)
    return candidates[0] if candidates else None


def main() -> None:
    if len(sys.argv) > 1:
        csv_path = Path(sys.argv[1])
    else:
        csv_path = _find_csv()
        if not csv_path:
            log.error("No Crash_File*.csv found in ~/Downloads")
            sys.exit(1)
        log.info("Using: %s", csv_path)

    dot_index, state_index = ingest(csv_path)
    out_dir = Path(__file__).parent.parent / "data"
    write_outputs(dot_index, state_index, out_dir)
    log.info("Done.")


if __name__ == "__main__":
    main()
