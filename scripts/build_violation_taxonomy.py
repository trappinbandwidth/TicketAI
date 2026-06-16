#!/usr/bin/env python3
"""
Extract CDL-relevant violation descriptions from the Kaggle CSV and
produce agents/violation_taxonomy.json — a lookup the AI can reference
to normalize violation text it reads off a ticket.

Usage:
  python scripts/build_violation_taxonomy.py [--csv PATH]
"""

import argparse, json, re
from collections import Counter
from pathlib import Path

DEFAULT_CSV = (
    Path.home()
    / ".cache/kagglehub/datasets/felix4guti"
    / "traffic-violations-in-usa/versions/1/Traffic_Violations.csv"
)
OUT_PATH = Path(__file__).parent.parent / "agents" / "violation_taxonomy.json"

# Map raw description patterns → normalized CDL category
CATEGORY_RULES = [
    ("SPEED",                       "Speeding"),
    ("SPEEDING",                    "Speeding"),
    ("EXCEEDING.*SPEED",            "Speeding"),
    ("FOLLOWING TOO CLOSE",         "Following Too Close"),
    ("LANE",                        "Improper Lane Change"),
    ("SIGNAL",                      "Failure to Signal"),
    ("STOP SIGN",                   "Failure to Stop"),
    ("RED LIGHT",                   "Red Light Violation"),
    ("TRAFFIC CONTROL",             "Failure to Obey Traffic Control"),
    ("SUSPENDED.*LICENSE",          "Driving on Suspended License"),
    ("SUSPENDED.*REGISTR",         "Suspended Registration"),
    ("NO.*LICENSE",                 "No Valid License"),
    ("WITHOUT.*LICENSE",            "No Valid License"),
    ("MEDICAL EXAMINER",            "Missing Medical Certificate"),
    ("MEDICAL CERT",                "Missing Medical Certificate"),
    ("LOGBOOK|LOG BOOK|HOS",        "Hours of Service Violation"),
    ("WEIGHT|OVERWEIGHT",           "Weight Violation"),
    ("HAZMAT|HAZARDOUS",            "HAZMAT Violation"),
    ("ALCOHOL|DUI|DWI|IMPAIRED",    "DUI / Impaired Driving"),
    ("SEATBELT|SEAT BELT|RESTRAIN", "Seatbelt Violation"),
    ("REGISTRATION",                "Registration Violation"),
    ("INSURANCE",                   "No Insurance"),
    ("HANDHELD|CELL PHONE|MOBILE",  "Cell Phone / Distracted Driving"),
    ("CARELESS|RECKLESS|NEGLIGENT", "Careless / Reckless Driving"),
    ("OVERSIZE|OVER SIZE",          "Oversize Load"),
    ("BRAKE",                       "Brake Violation"),
    ("LIGHT|HEADLAMP|TAILLIGHT",    "Lighting Violation"),
    ("TIRE",                        "Tire Violation"),
    ("INSPECTION",                  "Failed Inspection"),
]


def categorize(desc: str) -> str:
    upper = desc.upper()
    for pattern, category in CATEGORY_RULES:
        if re.search(pattern, upper):
            return category
    return "Other"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default=str(DEFAULT_CSV))
    args = p.parse_args()

    import pandas as pd

    print(f"Loading {args.csv} ...")
    df = pd.read_csv(args.csv, low_memory=False)

    # CDL-relevant subset
    cdl = df[
        (df["Commercial License"] == "Yes") | (df["Commercial Vehicle"] == "Yes")
    ].dropna(subset=["Description"])
    print(f"CDL/commercial rows: {len(cdl):,}")

    # Unique descriptions
    descs = cdl["Description"].str.strip().str.upper()
    counter = Counter(descs)

    # Build taxonomy
    categories: dict[str, list] = {}
    for desc, count in counter.most_common():
        cat = categorize(desc)
        if cat not in categories:
            categories[cat] = []
        categories[cat].append({"description": desc.title(), "count": count})

    # Sort categories by total count
    taxonomy = {}
    for cat in sorted(categories, key=lambda c: -sum(e["count"] for e in categories[c])):
        taxonomy[cat] = {
            "total_occurrences": sum(e["count"] for e in categories[cat]),
            "unique_descriptions": len(categories[cat]),
            "examples": [e["description"] for e in categories[cat][:5]],
        }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w") as f:
        json.dump(taxonomy, f, indent=2)

    print(f"\nViolation taxonomy → {OUT_PATH}")
    print(f"  {len(taxonomy)} categories  |  {len(counter):,} unique descriptions\n")
    for cat, info in list(taxonomy.items())[:15]:
        print(f"  {cat:<35}  {info['total_occurrences']:>6,} records  {info['unique_descriptions']} variants")


if __name__ == "__main__":
    main()
