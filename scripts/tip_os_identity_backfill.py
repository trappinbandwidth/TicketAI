#!/usr/bin/env python3
"""Dry-run/apply canonical identity links for existing role profiles."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.platform.migration import (  # noqa: E402
    ROLE_COLLECTIONS,
    ProfileRecord,
    apply_profile_backfill,
    plan_profile_backfill,
    write_migration_run,
)


def _db():
    from app.services import firebase_service

    firebase_service._init()
    if firebase_service._firestore_client is None:
        raise RuntimeError("Firestore is unavailable.")
    return firebase_service._firestore_client


def _load(db):
    profiles = []
    lookup = {}
    for collection in ROLE_COLLECTIONS.values():
        for snapshot in db.collection(collection).stream():
            data = snapshot.to_dict() or {}
            record = ProfileRecord(collection=collection, document_id=snapshot.id, data=data)
            profiles.append(record)
            lookup[(collection, snapshot.id)] = data
    principals = {snapshot.id: (snapshot.to_dict() or {}) for snapshot in db.collection("principals").stream()}
    return profiles, lookup, principals


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply safe create/link actions. Default is dry-run.")
    parser.add_argument("--confirm", default="", help="Required with --apply: TIP-OS-WP01")
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print aggregate results and conflicts without per-record actions.",
    )
    args = parser.parse_args()

    if args.apply and args.confirm != "TIP-OS-WP01":
        parser.error("--apply requires --confirm TIP-OS-WP01")
    if args.apply and os.getenv("TIP_OS_BACKFILL_APPLY_ENABLED", "false").lower() != "true":
        parser.error("Set TIP_OS_BACKFILL_APPLY_ENABLED=true to permit apply mode")

    db = _db()
    profiles, lookup, principals = _load(db)
    report = plan_profile_backfill(profiles, principals)
    safe_report = report.safe_dict()
    if args.summary_only:
        safe_report.pop("actions", None)
    output = {"mode": "apply" if args.apply else "dry-run", "report": safe_report}
    if args.apply:
        if report.conflict or report.invalid:
            output["apply"] = {"applied": 0, "blocked": True, "reason": "resolve_conflicts_and_invalid_records"}
        else:
            output["apply"] = apply_profile_backfill(db, report, lookup)
            output["apply"]["migration_run_id"] = write_migration_run(db, report, output["apply"])
    print(json.dumps(output, indent=2, sort_keys=True))
    return 2 if args.apply and (report.conflict or report.invalid) else 0


if __name__ == "__main__":
    raise SystemExit(main())
