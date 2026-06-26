"""
Roadside Inspection Activity ingestion.
Parses the FMCSA national summary Excel files (CY 2022–2026) into a structured
JSON used by Research Ron for defense context notes.

Usage:
    python3 scripts/ingest_inspection_stats.py
    python3 scripts/ingest_inspection_stats.py /path/to/file.xlsx

Output:
    data/inspection_national_stats.json
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Row labels in the FMCSA Excel report (order matters)
_ROW_LABELS = [
    "total_inspections",
    "with_no_violations",
    "with_violations",
    "with_oos_violations",
    "total_violations",
    "oos_violations",
    "other_violations",
]

# Calendar years the report covers (columns repeat in groups of 3: Fed/State/Total)
_YEARS = [2022, 2023, 2024, 2025, 2026]


def parse_excel(path: Path) -> dict:
    """
    Excel structure (0-indexed rows):
      Row 0: NaN | CY 2022 | NaN | NaN | CY 2023 | ...   (year spans)
      Row 1: NaN | CY 2022 | NaN | NaN | CY 2023 | ...  (year spans)
      Row 2: Activity Summary | Fed | State | Total | Fed | ...  (column headers)
      Row 3: Number of Inspections | 78687 | 2815204 | 2893891 | ...
      Row 4: With No Violations | ...
      Row 5: With Violations | ...
      Row 6: With OOS Violations | ...
      Row 7: Number of Violations | ...
      Row 8: OOS Violations | ...
      Row 9: Other Violations | ...
    """
    try:
        import pandas as pd
    except ImportError:
        log.error("Missing dependency. Run: python3 -m pip install pandas openpyxl")
        sys.exit(1)

    df = pd.read_excel(path, header=None)
    log.info("Excel shape: %s", df.shape)

    # Data rows are 3..9 (0-indexed), labels matched by position
    DATA_ROW_START = 3
    result: dict[int, dict] = {}

    for label_idx, label in enumerate(_ROW_LABELS):
        row_i = DATA_ROW_START + label_idx
        if row_i >= len(df):
            break
        row = df.iloc[row_i]

        for col_idx, year in enumerate(_YEARS):
            base_col = 1 + col_idx * 3  # Fed column for this year
            try:
                def to_int(v: object) -> int:
                    s = str(v).strip().replace(",", "").split(".")[0]
                    return int(s) if s.lstrip("-").isdigit() else 0

                fed   = to_int(row.iloc[base_col])
                state = to_int(row.iloc[base_col + 1])
                total = to_int(row.iloc[base_col + 2])
            except (IndexError, ValueError):
                continue

            if year not in result:
                result[year] = {}
            result[year][label] = {"federal": fed, "state": state, "total": total}

    # Derived rates
    for year, stats in result.items():
        ti = stats.get("total_inspections", {}).get("total", 0)
        if ti > 0:
            stats["violation_rate"] = round(
                stats.get("with_violations",     {}).get("total", 0) / ti, 4)
            stats["oos_rate"]       = round(
                stats.get("with_oos_violations", {}).get("total", 0) / ti, 4)
            stats["clean_rate"]     = round(
                stats.get("with_no_violations",  {}).get("total", 0) / ti, 4)

    return result


def _find_xlsx() -> Path | None:
    downloads = Path.home() / "Downloads"
    candidates = sorted(downloads.glob("roadside_inspection_activity*.xlsx"), reverse=True)
    return candidates[0] if candidates else None


def main() -> None:
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        path = _find_xlsx()
        if not path:
            log.error("No roadside_inspection_activity*.xlsx found in ~/Downloads")
            sys.exit(1)
        log.info("Using: %s", path)

    stats = parse_excel(path)

    out_path = Path(__file__).parent.parent / "data" / "inspection_national_stats.json"
    out_path.write_text(json.dumps(stats, indent=2))
    log.info("Wrote %s", out_path)

    # Summary
    print("\n── National inspection rates ──────────────────────────")
    print(f"  {'Year':<6}  {'Total':>10}  {'Violations':>10}  {'OOS':>8}  {'Clean':>8}")
    print("  " + "─" * 48)
    for year in sorted(stats.keys()):
        s = stats[year]
        total = s.get("total_inspections", {}).get("total", 0)
        viol  = round(s.get("violation_rate", 0) * 100, 1)
        oos   = round(s.get("oos_rate", 0) * 100, 1)
        clean = round(s.get("clean_rate", 0) * 100, 1)
        print(f"  {year:<6}  {total:>10,}  {viol:>9.1f}%  {oos:>7.1f}%  {clean:>7.1f}%")
    print()


if __name__ == "__main__":
    main()
