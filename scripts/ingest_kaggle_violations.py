"""
Kaggle Traffic Violations Ingestion — Rig Resolve Research Ron Phase 2 corpus builder.

Usage:
    pip install kagglehub[pandas-datasets] pandas
    python scripts/ingest_kaggle_violations.py

Outputs:
    data/violation_corpus.json      — Research Ron Phase 2 lookup: state+county+category → stats
    data/pricing_supplement.json    — pricing_table.json supplement with Kaggle-derived ranges
    data/violation_patterns.json    — keyword → category training pairs for lone_ranger
"""
from __future__ import annotations

import json
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Rig Resolve violation category picklist (19 categories) ───────────────────
RR_CATEGORIES = [
    "Driver license violation",
    "Alcohol / Drug related violation",
    "Reckless Driving",
    "Speeding (15+)",
    "Cell Phone",
    "Failure to yield to emergency vehicle",
    "Following too close",
    "Careless Driving",
    "Lane Violation",
    "Failure to Obey Traffic Control Device",
    "Too Fast for Conditions",
    "Speeding (1-14)",
    "Seatbelt",
    "ELD/Logs",
    "Equipment/Maintenance",
    "Registration Violations",
    "Overweight/Overlength",
    "Parking",
]

# ── Keyword → RR category mapping (applied to raw violation text) ─────────────
_CATEGORY_RULES: list[tuple[list[str], str]] = [
    (["dui", "dwi", "alcohol", "drug", "intox", "controlled substance"], "Alcohol / Drug related violation"),
    (["reckless"], "Reckless Driving"),
    (["speed", "radar", "lidar", "mph over"], "Speeding (15+)"),          # refined below
    (["cell phone", "handheld", "texting", "mobile phone", "electronic device"], "Cell Phone"),
    (["yield.*emerg", "emergency vehicle"], "Failure to yield to emergency vehicle"),
    (["follow.*close", "tailgat"], "Following too close"),
    (["careless", "negligent driv"], "Careless Driving"),
    (["lane", "improper lane", "failure to keep right", "improper pass"], "Lane Violation"),
    (["stop sign", "red light", "traffic signal", "traffic control", "traffic device",
      "fail.*obey", "disregard signal"], "Failure to Obey Traffic Control Device"),
    (["too fast for condition"], "Too Fast for Conditions"),
    (["seatbelt", "seat belt", "safety belt", "occupant restraint"], "Seatbelt"),
    (["eld", "log book", "hours of service", "hos violation", "driver record of duty"], "ELD/Logs"),
    (["equipment", "maintenance", "defective", "brake", "light", "tire", "inspection fail",
      "out of service"], "Equipment/Maintenance"),
    (["registr", "license plate", "tag expired", "no registration"], "Registration Violations"),
    (["overweight", "overlength", "oversize", "permit load"], "Overweight/Overlength"),
    (["park", "standing", "stopping"], "Parking"),
    (["license", "cdl", "endorsement", "no valid", "suspended license",
      "revoked", "disqualif"], "Driver license violation"),
]

# CDL / commercial vehicle indicator keywords
_CDL_KEYWORDS = [
    "commercial", "cdl", "truck", "semi", "tractor", "trailer",
    "18-wheel", "class a", "class b", "18 wheel", "motor carrier",
    "hazmat", "haz mat", "tanker", "double", "triple",
]

# State abbreviation → full name
_STATE_NAMES: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}


def _map_category(raw: object) -> str:
    """Map a raw violation description to a Rig Resolve category."""
    if not isinstance(raw, str):
        return ""
    text = raw.lower()

    # Speed-specific: try to extract mph over limit
    speed_match = re.search(r"(\d+)\s*mph?\s*(?:over|above)", text)
    if speed_match or re.search(r"\bspeed\b|\bradar\b|\blidar\b", text):
        try:
            over = int(speed_match.group(1)) if speed_match else 0
            return "Speeding (15+)" if over >= 15 else "Speeding (1-14)"
        except (AttributeError, ValueError):
            return "Speeding (15+)"  # default if unclear

    for patterns, category in _CATEGORY_RULES:
        for pat in patterns:
            if re.search(pat, text):
                return category

    return ""  # unmapped — will be dropped


def _is_cdl_relevant(row: dict[str, Any], text_cols: list[str]) -> bool:
    """Return True if the record has any CDL/commercial indicator."""
    combined = " ".join(str(row.get(c, "")).lower() for c in text_cols)
    return any(kw in combined for kw in _CDL_KEYWORDS)


def _normalize_state(val: str) -> str:
    """Normalize state abbreviation or name to full name."""
    v = (val or "").strip().upper()
    if v in _STATE_NAMES:
        return _STATE_NAMES[v]
    # Already a full name?
    for full in _STATE_NAMES.values():
        if full.upper() == v:
            return full
    return val.strip().title()


def _normalize_outcome(row: dict[str, Any], type_col: str | None) -> str:
    """Return 'citation' | 'warning' | 'arrest' | 'other'."""
    if not type_col:
        return "other"
    v = str(row.get(type_col, "")).lower()
    if "citation" in v or "fine" in v or "charge" in v:
        return "citation"
    if "warning" in v:
        return "warning"
    if "arrest" in v:
        return "arrest"
    return "other"


def build_corpus(df: Any) -> tuple[dict, dict, list]:
    """
    Returns:
      violation_corpus  — {state: {category: {county_stats, outcome_dist, count}}}
      pricing_supplement — {state: {category: {count, citation_rate, source}}}
      training_pairs     — [{text, category}]  for lone_ranger fine-tuning
    """
    import pandas as pd  # noqa: PLC0415

    log.info("Dataset shape: %s  columns: %s", df.shape, list(df.columns))

    # ── Detect column names ───────────────────────────────────────────────────
    cols = {c.lower(): c for c in df.columns}

    def col(*candidates: str) -> str | None:
        for c in candidates:
            if c in cols:
                return cols[c]
        return None

    desc_col       = col("description", "violation", "violation_type", "charge_description",
                         "violation description", "subtype", "violation_desc")
    state_col      = col("state", "driver_state", "dl_state", "dl state", "state_code")
    # Prefer SubAgency (district/precinct) as the county-level grouping for this dataset
    county_col     = col("subagency", "county", "county_name", "jurisdiction")
    type_col       = col("violation type", "type", "violation_type", "outcome",
                         "result", "disposition", "arrest type")
    # Explicit CDL indicator columns (present in Montgomery County dataset)
    cdl_lic_col    = col("commercial license", "cdl", "commercial_license")
    cdl_veh_col    = col("commercial vehicle", "commercial_vehicle")
    hazmat_col     = col("hazmat", "haz mat", "hazardous")

    # Columns to scan for CDL keywords (fallback when no explicit column)
    text_cols = [c for c in [desc_col, type_col, col("make", "vehicle_make"),
                              col("vehicletype", "vehicle_type")] if c]

    log.info(
        "Mapped — description=%r state=%r county=%r type=%r cdl_lic=%r cdl_veh=%r",
        desc_col, state_col, county_col, type_col, cdl_lic_col, cdl_veh_col,
    )

    if not desc_col:
        log.error("Cannot find a description/violation column. Columns available: %s", list(df.columns))
        sys.exit(1)

    # ── Pass 1: map categories ────────────────────────────────────────────────
    log.info("Mapping violation categories …")
    df = df.copy()
    df["_rr_category"] = df[desc_col].apply(_map_category)
    df = df[df["_rr_category"] != ""]  # drop unmapped
    log.info("Mapped %d / original rows to RR categories", len(df))

    # ── Pass 2: CDL filter ────────────────────────────────────────────────────
    log.info("Filtering for CDL-relevant records …")

    def _is_cdl_row(r: dict[str, Any]) -> bool:
        # Use explicit boolean columns when available (Montgomery County dataset)
        for col_name in [cdl_lic_col, cdl_veh_col, hazmat_col]:
            if col_name and str(r.get(col_name, "")).strip().lower() in ("yes", "true", "1", "y"):
                return True
        # Keyword fallback for datasets without explicit columns
        return _is_cdl_relevant(r, text_cols)

    records = df.to_dict("records")
    cdl_records = [r for r in records if _is_cdl_row(r)]
    log.info("CDL-relevant: %d / %d (%.1f%%)", len(cdl_records), len(records),
             100 * len(cdl_records) / max(len(records), 1))

    if not cdl_records:
        log.warning(
            "No CDL-specific records found. Using all records with category mapping. "
            "This dataset may not have commercial vehicle data — corpus will cover all violations."
        )
        cdl_records = records  # fall back to all

    # ── Aggregate ─────────────────────────────────────────────────────────────
    # Structure:
    # corpus[state][category] = {
    #   count, county_stats: {county: count}, outcome_dist: {citation/warning/...: count}
    # }
    corpus: dict[str, dict[str, Any]]   = defaultdict(lambda: defaultdict(lambda: {
        "count": 0,
        "county_stats": defaultdict(int),
        "outcome_dist": defaultdict(int),
    }))
    training_pairs: list[dict]           = []
    seen_texts: set[str]                 = set()

    for r in cdl_records:
        state    = _normalize_state(str(r.get(state_col, "") if state_col else "")) or "Unknown"
        county   = str(r.get(county_col, "") if county_col else "").strip().title() or "Unknown"
        category = r["_rr_category"]
        outcome  = _normalize_outcome(r, type_col)
        raw_desc = str(r.get(desc_col, "")).strip()

        bucket = corpus[state][category]
        bucket["count"] += 1
        bucket["county_stats"][county] += 1
        bucket["outcome_dist"][outcome] += 1

        # Training pair (deduplicated by text)
        text_key = raw_desc.lower()[:120]
        if raw_desc and text_key not in seen_texts and len(training_pairs) < 50_000:
            seen_texts.add(text_key)
            training_pairs.append({"text": raw_desc, "category": category, "state": state})

    # ── Finalise corpus ───────────────────────────────────────────────────────
    HIGH_RISK_CATEGORIES = {
        "Alcohol / Drug related violation", "Reckless Driving", "Speeding (15+)",
        "Driver license violation",
    }

    violation_corpus: dict[str, Any] = {}
    pricing_supplement: dict[str, Any] = {}

    for state, cats in corpus.items():
        violation_corpus[state] = {}
        pricing_supplement[state] = {}

        for cat, data in cats.items():
            total  = data["count"]
            county_stats = dict(
                sorted(data["county_stats"].items(), key=lambda x: -x[1])[:20]
            )
            outcome_dist = dict(data["outcome_dist"])
            citation_ct  = outcome_dist.get("citation", 0)
            citation_rate = round(citation_ct / total, 3) if total > 0 else 0.0
            top_counties = [k for k, _ in list(county_stats.items())[:5]]

            violation_corpus[state][cat] = {
                "count": total,
                "top_counties": top_counties,
                "county_stats": county_stats,
                "outcome_dist": outcome_dist,
                "citation_rate": citation_rate,
                "high_risk": cat in HIGH_RISK_CATEGORIES,
            }

            pricing_supplement[state][cat] = {
                "count": total,
                "citation_rate": citation_rate,
                "high_risk": cat in HIGH_RISK_CATEGORIES,
                "source": "kaggle_traffic_violations_usa",
            }

    return dict(violation_corpus), dict(pricing_supplement), training_pairs


def write_outputs(
    corpus: dict,
    pricing: dict,
    training: list,
    out_dir: Path,
) -> None:
    out_dir.mkdir(exist_ok=True)

    corpus_path  = out_dir / "violation_corpus.json"
    pricing_path = out_dir / "pricing_supplement.json"
    train_path   = out_dir / "violation_training_pairs.jsonl"

    corpus_path.write_text(json.dumps(corpus, indent=2))
    log.info("Wrote %s  (%d states)", corpus_path, len(corpus))

    pricing_path.write_text(json.dumps(pricing, indent=2))
    log.info("Wrote %s", pricing_path)

    with train_path.open("w") as f:
        for pair in training:
            f.write(json.dumps(pair) + "\n")
    log.info("Wrote %s  (%d pairs)", train_path, len(training))

    # Print coverage summary
    print("\n── Coverage summary ────────────────────────────────────")
    state_rows = []
    for state, cats in sorted(corpus.items()):
        total = sum(c["count"] for c in cats.values())
        top_cat = max(cats.items(), key=lambda x: x[1]["count"])[0] if cats else "—"
        state_rows.append((state, total, len(cats), top_cat))
    state_rows.sort(key=lambda x: -x[1])

    print(f"{'State':<25} {'Records':>8}  {'Categories':>10}  Top category")
    print("─" * 80)
    for state, total, ncats, top in state_rows[:30]:
        print(f"{state:<25} {total:>8,}  {ncats:>10}  {top}")
    if len(state_rows) > 30:
        print(f"  … and {len(state_rows) - 30} more states")

    print(f"\nTotal states: {len(corpus)}")
    print(f"Total records: {sum(sum(c['count'] for c in cats.values()) for cats in corpus.values()):,}")
    print(f"Training pairs: {len(training):,}")
    print("────────────────────────────────────────────────────────\n")


def main() -> None:
    try:
        import kagglehub
        import pandas as pd  # noqa: F401 (used inside build_corpus via df.to_dict)
    except ImportError:
        log.error("Missing dependencies. Run: python3 -m pip install 'kagglehub[pandas-datasets]' pandas")
        sys.exit(1)

    log.info("Downloading dataset from Kaggle …")
    # Skip checksum validation — the GCS MD5 header is unreliable on partial downloads.
    import os as _os
    _os.environ.setdefault("KAGGLE_DATASETS_CHECKSUM_VERIFICATION", "0")
    # Download returns the local directory; read the CSV directly to avoid
    # kagglehub's checksum re-validation on already-cached files.
    dataset_dir = Path(kagglehub.dataset_download("felix4guti/traffic-violations-in-usa"))
    csv_path = dataset_dir / "Traffic_Violations.csv"
    if not csv_path.exists():
        # Fallback: find any CSV in the directory
        csvs = list(dataset_dir.glob("**/*.csv"))
        if not csvs:
            log.error("No CSV found in dataset directory: %s", dataset_dir)
            sys.exit(1)
        csv_path = csvs[0]
        log.info("Using CSV: %s", csv_path)

    log.info("Loading %s …", csv_path)
    import pandas as pd  # noqa: PLC0415
    df = pd.read_csv(csv_path, low_memory=False)
    log.info("Dataset loaded: %s rows × %s columns", len(df), len(df.columns))
    log.info("Columns: %s", list(df.columns))
    log.info("First record:\n%s", df.iloc[0].to_dict() if len(df) > 0 else "(empty)")

    corpus, pricing, training = build_corpus(df)

    out_dir = Path(__file__).parent.parent / "data"
    write_outputs(corpus, pricing, training, out_dir)
    log.info("Done. Corpus ready for Research Ron Phase 2.")


if __name__ == "__main__":
    main()
