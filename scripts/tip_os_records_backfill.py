#!/usr/bin/env python3
"""Dry-run/apply legacy ticket projections into canonical Driver Cloud records."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.platform.record_migration import (  # noqa: E402
    MIGRATION_VERSION,
    LegacyTicket,
    plan_ticket_projections,
)
from app.platform.records import CanonicalRecord, raw_payload_hash  # noqa: E402
from app.platform.models import utc_now  # noqa: E402


def db_client():
    from app.services import firebase_service

    firebase_service._init()
    if firebase_service._firestore_client is None:
        raise RuntimeError("Firestore is unavailable.")
    return firebase_service._firestore_client


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    if args.apply and args.confirm != "TIP-OS-WP02":
        parser.error("--apply requires --confirm TIP-OS-WP02")
    if args.apply and os.getenv("TIP_OS_RECORD_BACKFILL_APPLY_ENABLED", "false").lower() != "true":
        parser.error("Set TIP_OS_RECORD_BACKFILL_APPLY_ENABLED=true to permit apply mode")

    db = db_client()
    tickets = [
        LegacyTicket(snapshot.id, snapshot.to_dict() or {})
        for snapshot in db.collection("tickets").stream()
    ]
    existing = {
        snapshot.id: snapshot.to_dict() or {}
        for snapshot in db.collection("canonical_records").stream()
    }
    projections = plan_ticket_projections(tickets, existing)
    counts = {
        outcome: sum(1 for item in projections if item.outcome == outcome)
        for outcome in ("create", "unchanged", "conflict", "invalid")
    }
    output = {
        "mode": "apply" if args.apply else "dry-run",
        "migration_version": MIGRATION_VERSION,
        "scanned": len(projections),
        **counts,
    }
    if not args.summary_only:
        output["projections"] = [item.safe_dict() for item in projections]

    if args.apply:
        if counts["conflict"] or counts["invalid"]:
            output["apply"] = {"blocked": True, "applied": 0}
        else:
            applied = 0
            for item in projections:
                if item.outcome != "create" or item.body is None:
                    continue
                body = item.body
                record = CanonicalRecord(
                    id=item.record_id,
                    subject_principal_id=item.subject_principal_id,
                    created_by="migration:tip-os-wp02",
                    raw_sha256=raw_payload_hash(body.raw),
                    **body.model_dump(),
                )
                db.collection("canonical_records").document(record.id).set(record.model_dump(mode="json"))
                applied += 1
            output["apply"] = {"blocked": False, "applied": applied}
            run_id = f"migration_{MIGRATION_VERSION}"
            db.collection("migration_runs").document(run_id).set({
                "id": run_id,
                "migration_version": MIGRATION_VERSION,
                "counts": output,
                "created_at": utc_now().isoformat(),
                "rollback": {"delete_where": {"created_by": "migration:tip-os-wp02"}},
            })
    print(json.dumps(output, indent=2, sort_keys=True))
    return 2 if args.apply and (counts["conflict"] or counts["invalid"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
