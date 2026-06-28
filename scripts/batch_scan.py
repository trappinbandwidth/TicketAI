#!/usr/bin/env python3
"""
Grouped batch ticket scanner — Rig Resolve training data ingestion.

Parses filenames using the convention:
  [Driver Name] [Date] [State] [DocType] [page#].ext

Groups multi-page tickets belonging to the same driver+event into a single
API call (the /api/v1/process endpoint accepts up to 10 images per ticket).

Unidentified files (UUID names, fax artifacts, HEIC, generic names) are
queued individually so the AI can classify them.

Scannable doc types : TK  IR  MVR  KT  DOC  CRASH
Skipped             : legal docs, pleas, dispositions, receipts, insurance

Usage:
  # Dry run — shows plan, posts nothing
  python scripts/batch_scan.py --dir "/path/to/batch" --dry-run

  # Real scan against deployed service
  python scripts/batch_scan.py \\
    --dir "/Users/digitalmercenary/CDL_Defense/ai tickets samples/20260627 - Batch 1" \\
    --api https://ai-ticket-engine-kajugdk3nq-uc.a.run.app \\
    --out scripts/batch_results.json

  # Resume a partial run (already-done scans are skipped automatically)
  python scripts/batch_scan.py --dir "..." --api "..."

Requires: requests  (pip install requests)
HEIC conversion uses macOS `sips` — no extra install needed on Mac.
"""

from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from collections import defaultdict
from pathlib import Path

import requests

# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_DIR = Path("/Users/digitalmercenary/CDL_Defense/ai tickets samples/20260627 - Batch 1")
DEFAULT_API = "https://ai-ticket-engine-kajugdk3nq-uc.a.run.app"
DEFAULT_OUT = Path(__file__).parent / "batch_results.json"
def _load_api_key() -> str:
    key = os.getenv("API_KEY", "")
    if key:
        return key
    # Try loading from .env in repo root
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("API_KEY="):
                return line.split("=", 1)[1].strip()
    return "cdl-local-dev"

API_KEY = _load_api_key()
HEADERS     = {"x-api-key": API_KEY}

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
PDF_EXTS   = {".pdf"}
HEIC_EXTS  = {".heic"}
SCAN_EXTS  = IMAGE_EXTS | PDF_EXTS

# ── Filename intelligence ─────────────────────────────────────────────────────
US_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY",
}

DOC_TYPE_TOKENS = ["MVR","PSP","TKs","TK","IR","DOC","KT","CRASH","Tckt","tic"]

# Normalize alternate token spellings → canonical
DOC_TYPE_NORM = {
    "TKs": "TK", "Tckt": "TK", "tic": "TK", "Inspection": "IR",
}

# Keywords that mark a file as non-scannable legal/admin doc
SKIP_KEYWORDS = [
    "plea", "dispo", "disposition", "case over", "closing letter",
    "invoice", "waiver", "agreement", "order forfeiting", "municipal case",
    "payment receipt", "pti", "mdjdocketsheet", "oscn", "courtnet",
    "docket sheet", "docket", "case detail", "confirmation letter",
    "prosecutor", "bossier parish", "trial waiver", "court summary",
    "htoo closing", "cdl legal mail", "tire receipt", "repair_tire",
    "plea in absentia", "plea offer", "plea agreement",
    "case over -", "case over-", "vitalii dispo", "pugh dispo",
    "pugh crisp", "jerrell pugh-crisp", "khayibaev disposition",
    "ga dispo", "order disposition", "01.09.2025 payment",
    "sc- elam", "case over - elam", "case over - smith",
    "case_ 24", "case_24", "insurance 2", "insurance 3",
    "insurance.png", "court summary", "order setting aside",
    "notice to dot",
]

# Files we try to scan even though driver name is missing —
# the AI will classify the document type and whatever it finds goes into the queue.
TRY_SCAN_UNKNOWNS = True

# Known driver overrides — maps filename substring → driver name
# Fills gaps where the parser can't extract a name from the stem.
DRIVER_OVERRIDES: dict[str, str] = {
    "8.20.19 timothy smith":        "Timothy Smith",
    "andre roach mvr":              "Andre Roach",
    "antonio bruno mvr":            "Antonio Bruno",
    "crystal johnson psp":          "Crystal Johnson",
    "jozef hubacek mvr":            "Jozef Hubacek",
    "kaseem johnson - pa - ir":     "KASEEM JOHNSON",
    "mvr for valeriy barkhudaryan": "Valeriy Barkhudaryan",
    "muaiyed al nassih ir":         "Muaiyed Al Nassih",
    "ncdot-record":                 "NC DOT Driver Record",
    "1-ncdot-record":               "NC DOT Driver Record",
    "ahmed abdi driving record":    "Abdi Ahmed",
    "thapa soti nabin mvr":         "NABIN THAPA SOTI",
    "ronald forrest mvr":           "Ronald Forrest",
    "pre emply mvr blasco":         "Ion Blasco",
    "roman gamski pa tic":          "Roman Gamski",
    "roach_000643":                 "Andre Roach",
    "roudeline zephirin id":        "Roudeline Zepherin",
    "txdpslicenseemanager":         "TX DPS Driver Record",
    "salvatore coladonato":         "Salvatore Coladonato",
    "mesfin ashsmte md":            "Mesfin Ashsmte",
    "leonel ayuso hearing":         "Leonel Ayuso",
    "charles ticket":               "Charles (Unknown Last Name)",
    "hossain ticket":               "Hossain (Unknown Last Name)",
    "shannon perkins":              "Shannon Perkins",
    "eliana a":                     "Eliana Amortegui Barraza",
    "frelon":                       "Frelon (Unknown First Name)",
    "gumje-citation":               "GUMJE (Unknown Full Name)",
    "ali nc":                       "Ali (Unknown Last Name - NC)",
    "goranlap":                     "GoranLapusina",
    "houssein jawhar pa inspection":"Houssein Jawhar",
    "houssein jawhar pa tckt":      "Houssein Jawhar",
    "jorge garcia 3.24 or kt":      "Jorge Garcia",
    "crystal johnson - wy":         "Crystal Johnson",
    "oluyesi_oyedele_yemc":         "Oluyesi Oyedele",
    "oluyesi_oyedele_.":            "Oluyesi Oyedele",
    "skmbt":                        "Unknown - Konica Scan",
    "camscanner 12-19-2023":        "Unknown - CamScanner",
    "xerox scan":                   "Unknown - Xerox Scan",
}

# Doc type override for specific filenames
DOCTYPE_OVERRIDES: dict[str, str] = {
    "8.20.19 timothy smith tckt":   "TK",
    "andre roach mvr":              "MVR",
    "antonio bruno mvr":            "MVR",
    "crystal johnson psp":          "PSP",
    "jozef hubacek mvr":            "MVR",
    "mvr for valeriy barkhudaryan": "MVR",
    "thapa soti nabin mvr":         "MVR",
    "ronald forrest mvr":           "MVR",
    "ahmed abdi driving record":    "MVR",
    "ncdot-record":                 "MVR",
    "1-ncdot-record":               "MVR",
    "pre emply mvr blasco":         "MVR",
    "houssein jawhar pa inspection":"IR",
    "houssein jawhar pa tckt":      "TK",
    "roman gamski pa tic":          "TK",
    "charles ticket":               "TK",
    "hossain ticket":               "TK",
    "leonel ayuso hearing":         "DOC",
    "jorge garcia 3.24 or kt":      "KT",
    "kaseem johnson - pa - ir":     "IR",
    "roudeline zephirin id":        "DOC",
    "txdpslicenseemanager":         "MVR",
    "crystal johnson - wy":         "TK",
}

DATE_RE = re.compile(
    r'\b(\d{1,2}[.\-]\d{1,2}[.\-]\d{2,4}|\d{2}\.\d{2}\.\d{4})\b'
)
PAGE_RE  = re.compile(r'\((\d+)\)$|[\s_](\d+)$')
UUID_RE  = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-', re.IGNORECASE)
FAX_RE   = re.compile(r'^\d{7,}$')


# ── Filename classification ───────────────────────────────────────────────────

def should_skip(filename: str) -> tuple[bool, str]:
    """Return (True, reason) for files that should never be scanned."""
    lower = filename.lower()
    for kw in SKIP_KEYWORDS:
        if kw in lower:
            return True, f"legal/admin keyword '{kw}'"
    stem = Path(filename).stem.lower()
    if stem.startswith("child seat"):
        return True, "child seat photo"
    if stem.startswith("equipment"):
        return True, "equipment photo"
    if "repair_tire" in stem or "tire receipt" in stem:
        return True, "tire receipt"
    if stem.startswith("insurance"):
        return True, "insurance document"
    if stem.startswith("screenshot_2026042"):
        return True, "phone screenshot (messages/gmail)"
    if "gmail" in stem or "messages" in stem:
        return True, "messaging screenshot"
    if stem in ("insurance", "insurance 2", "insurance 3"):
        return True, "insurance doc"
    return False, ""


def _override_lookup(lower_stem: str, override_dict: dict) -> str | None:
    for key, val in override_dict.items():
        if key in lower_stem:
            return val
    return None


def parse_filename(filename: str) -> dict:
    """
    Parse a filename into structured fields.
    Returns: {name, date, state, doc_type, page, is_unknown}
    """
    stem  = Path(filename).stem
    lower = stem.lower()

    info: dict = {
        "name": None, "date": None, "state": None,
        "doc_type": None, "page": 1, "is_unknown": False,
    }

    # Check override tables first
    name_override = _override_lookup(lower, DRIVER_OVERRIDES)
    if name_override:
        info["name"] = name_override

    dt_override = _override_lookup(lower, DOCTYPE_OVERRIDES)
    if dt_override:
        info["doc_type"] = dt_override

    # Detect UUID / fax / timestamp names → unknown
    if UUID_RE.match(stem) or FAX_RE.match(stem):
        info["is_unknown"] = True
        info["name"] = info["name"] or f"Unknown-{stem[:8]}"
        return info

    # Find date
    dm = DATE_RE.search(stem)
    if dm:
        info["date"] = dm.group()
        name_part = stem[:dm.start()].strip(" -_")
        after     = stem[dm.end():]
    else:
        name_part = stem
        after     = ""

    # Find US state abbreviation after date
    if not info.get("state"):
        for tok in re.findall(r'\b([A-Za-z]{2})\b', after):
            if tok.upper() in US_STATES:
                info["state"] = tok.upper()
                break

    # Find doc type
    if not info["doc_type"]:
        for dt in DOC_TYPE_TOKENS:
            if re.search(r'\b' + re.escape(dt) + r'\b', after, re.IGNORECASE):
                info["doc_type"] = DOC_TYPE_NORM.get(dt, dt.upper())
                break

    # Find page number
    pm = PAGE_RE.search(stem)
    if pm:
        info["page"] = int(pm.group(1) or pm.group(2))

    # Driver name
    if not info["name"]:
        cleaned = re.sub(r'\s+', ' ', name_part).strip()
        info["name"] = cleaned if cleaned else "Unknown"

    # Flag as unknown if no identifiable driver name
    if not info["name"] or info["name"] in ("Unknown", ""):
        info["is_unknown"] = True

    return info


# ── HEIC conversion ───────────────────────────────────────────────────────────

def convert_heic(src: Path, tmp_dir: Path) -> Path | None:
    """Convert HEIC → JPEG using macOS sips. Returns path to JPEG or None."""
    dst = tmp_dir / (src.stem + ".jpg")
    try:
        r = subprocess.run(
            ["sips", "-s", "format", "jpeg", str(src), "--out", str(dst)],
            capture_output=True, timeout=30,
        )
        if r.returncode == 0 and dst.exists():
            return dst
    except Exception as e:
        print(f"  [HEIC] sips failed for {src.name}: {e}")
    return None


# ── File grouping ─────────────────────────────────────────────────────────────

def group_files(batch_dir: Path, tmp_dir: Path) -> tuple[dict, list, list]:
    """
    Walk batch_dir and return:
      driver_groups : {driver_key → {name, scans: [{doc_type, state, date, pages, ticket_id}]}}
      unknown_scans : [{name, file, ticket_id}]   — scan-and-classify
      skip_log      : [{file, reason}]
    """
    driver_groups: dict = defaultdict(lambda: {"name": None, "scans": []})
    page_buckets: dict  = defaultdict(list)   # (dk, doc_type, date, state) → [(page, Path)]
    unknown_scans: list = []
    skip_log: list      = []

    for f in sorted(batch_dir.iterdir()):
        if f.is_dir():
            continue

        ext = f.suffix.lower()

        # Convert HEIC → JPEG
        if ext in HEIC_EXTS:
            converted = convert_heic(f, tmp_dir)
            if converted:
                print(f"  [HEIC] {f.name} → {converted.name}")
                f, ext = converted, ".jpg"
            else:
                skip_log.append({"file": f.name, "reason": "HEIC conversion failed"})
                continue

        if ext not in SCAN_EXTS:
            skip_log.append({"file": f.name, "reason": f"unsupported extension {ext}"})
            continue

        skip, reason = should_skip(f.name)
        if skip:
            skip_log.append({"file": f.name, "reason": reason})
            continue

        info = parse_filename(f.name)

        # UUID / fax / completely unidentifiable → try-scan-unknown
        if info["is_unknown"] and TRY_SCAN_UNKNOWNS:
            unknown_scans.append({
                "label": f.name,
                "file":  f,
                "ticket_id": str(uuid.uuid4()),
            })
            continue

        dk = (info["name"] or "Unknown").upper().strip()
        if driver_groups[dk]["name"] is None:
            driver_groups[dk]["name"] = info["name"]

        bucket = (dk, info["doc_type"] or "UNK", info["date"] or "nodate", info["state"] or "XX")
        page_buckets[bucket].append((info["page"], f))

    # Sort pages within each bucket and build scan entries
    for (dk, doc_type, date, state), pages in page_buckets.items():
        sorted_pages = [p for _, p in sorted(pages)]
        driver_groups[dk]["scans"].append({
            "doc_type": doc_type,
            "date":     date,
            "state":    state,
            "pages":    sorted_pages,
            "ticket_id": str(uuid.uuid4()),
        })

    return dict(driver_groups), unknown_scans, skip_log


# ── API posting ───────────────────────────────────────────────────────────────

def post_scan(api_base: str, files: list[Path], driver_name: str, ticket_id: str) -> dict:
    """Post one ticket (one or more page files) to the process endpoint."""
    url = f"{api_base}/api/v1/process"
    multipart = []
    handles   = []
    try:
        for p in files:
            ext = p.suffix.lower()
            mime = ("image/jpeg" if ext in (".jpg", ".jpeg")
                    else "image/png" if ext == ".png"
                    else "application/pdf")
            fh = p.open("rb")
            handles.append(fh)
            multipart.append(("files", (p.name, fh, mime)))

        data = {
            "driver_name":    driver_name,
            "ticket_id":      ticket_id,
            "source":         "driver_upload",
            "prompt_version": "v2",
        }
        resp = requests.post(url, headers=HEADERS, files=multipart, data=data, timeout=300)
        resp.raise_for_status()
        return resp.json()
    finally:
        for fh in handles:
            try: fh.close()
            except Exception: pass


def summarise(data: dict) -> dict:
    """Extract key metrics from a scan response for the results log."""
    result_obj  = data.get("result") or {}
    fields      = {k: v for k, v in result_obj.items()
                   if isinstance(v, dict) and "confidence_score" in v}
    applicable  = {k: v for k, v in fields.items()
                   if v.get("value") or v.get("confidence_score", 0) > 0}
    scores      = [v["confidence_score"] for v in applicable.values()]
    avg_conf    = round(sum(scores) / len(scores), 3) if scores else 0.0
    return {
        "pass_status":          data.get("pass_status"),
        "queue_id":             data.get("queue_id"),
        "urgency":              data.get("urgency_level"),
        "completeness":         data.get("completeness_score"),
        "avg_confidence":       avg_conf,
        "fields_filled":        sum(1 for v in applicable.values() if v.get("value")),
        "fields_total":         len(fields),
        "low_confidence_fields": data.get("low_confidence_fields", []),
        "missing_fields":       data.get("missing_fields", []),
        "file_type":            (result_obj.get("file_type") or "?"),
        "violation":            (result_obj.get("Violation_Category__c") or {}).get("value", ""),
        "state":                (result_obj.get("Ticket_State__c") or {}).get("value", ""),
        "court_date":           (result_obj.get("Court_Date__c") or {}).get("value", ""),
        "court_time":           (result_obj.get("Court_Time__c") or {}).get("value", ""),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Rig Resolve grouped batch scanner")
    ap.add_argument("--dir",     default=str(DEFAULT_DIR),  help="Batch folder path")
    ap.add_argument("--api",     default=DEFAULT_API,       help="API base URL")
    ap.add_argument("--out",     default=str(DEFAULT_OUT),  help="Results JSON path")
    ap.add_argument("--limit",   type=int, default=0,       help="Max scans to run (0=all)")
    ap.add_argument("--delay",   type=float, default=2.5,   help="Seconds between scans")
    ap.add_argument("--dry-run", action="store_true",       help="Show plan, post nothing")
    ap.add_argument("--unknown-only", action="store_true",  help="Only scan unidentified files")
    args = ap.parse_args()

    batch_dir = Path(args.dir)
    out_path  = Path(args.out)

    if not batch_dir.exists():
        print(f"ERROR: batch directory not found: {batch_dir}")
        sys.exit(1)

    tmp_dir = Path(tempfile.mkdtemp(prefix="rr_batch_"))
    print(f"Parsing {batch_dir.name} ...")
    driver_groups, unknown_scans, skip_log = group_files(batch_dir, tmp_dir)

    # Load existing results for resume
    results: dict = {}
    if out_path.exists():
        with out_path.open() as fh:
            results = json.load(fh)
        existing = len(results)
        print(f"Resuming — {existing} scans already in results file")

    # Build scan queue
    scan_queue: list[dict] = []

    if not args.unknown_only:
        for dk, dv in sorted(driver_groups.items()):
            for scan in dv["scans"]:
                scan_queue.append({
                    "key":         f"{dv['name']}|{scan['doc_type']}|{scan['date']}|{scan['state']}",
                    "driver":      dv["name"],
                    "doc_type":    scan["doc_type"],
                    "state":       scan["state"],
                    "date":        scan["date"],
                    "pages":       scan["pages"],
                    "ticket_id":   scan["ticket_id"],
                    "is_unknown":  False,
                })

    # Unknown files always appended after named drivers
    for u in unknown_scans:
        scan_queue.append({
            "key":        f"UNKNOWN|{u['label']}",
            "driver":     f"Unknown — {u['label']}",
            "doc_type":   "?",
            "state":      "?",
            "date":       "?",
            "pages":      [u["file"]],
            "ticket_id":  u["ticket_id"],
            "is_unknown": True,
        })

    if args.limit:
        scan_queue = scan_queue[:args.limit]

    total = len(scan_queue)
    already_done = sum(1 for s in scan_queue if results.get(s["key"], {}).get("status") == "ok")

    print(f"\n{'='*60}")
    print(f"Named drivers   : {len(driver_groups)}")
    print(f"Known scans     : {sum(len(v['scans']) for v in driver_groups.values())}")
    print(f"Unknown scans   : {len(unknown_scans)}")
    print(f"Skipped files   : {len(skip_log)}")
    print(f"Queue total     : {total}  ({already_done} already done)")
    print(f"{'='*60}\n")

    if args.dry_run:
        print("DRY RUN — scan plan\n")
        for s in scan_queue:
            done_tag = " (done)" if s["key"] in results else ""
            dt_tag = "[?]" if s["is_unknown"] else f"[{s['doc_type']}]"
            print(f"  {dt_tag:<5} {s['driver']:<40} {s['state']:<4} {s['date']:<12} {len(s['pages'])}pg{done_tag}")
            if len(s["pages"]) > 1 or s["is_unknown"]:
                for p in s["pages"]:
                    print(f"         {p.name}")

        print(f"\nSkipped ({len(skip_log)} files):")
        for sl in skip_log:
            print(f"  {sl['file'][:55]:<55}  → {sl['reason']}")
        return

    # ── Execute scans ────────────────────────────────────────────────────────
    done = errors = skipped = 0
    for i, scan in enumerate(scan_queue, 1):
        if results.get(scan["key"], {}).get("status") == "ok":
            skipped += 1
            continue

        label = (f"[{scan['doc_type']}] {scan['driver']}"
                 f" {scan['state']} {scan['date']}")
        print(f"[{i:3d}/{total}] {label[:65]:<65}", end=" ", flush=True)

        t0 = time.time()
        try:
            data    = post_scan(args.api, scan["pages"], scan["driver"], scan["ticket_id"])
            elapsed = time.time() - t0
            summ    = summarise(data)

            results[scan["key"]] = {
                "status":    "ok",
                "driver":    scan["driver"],
                "doc_type":  scan["doc_type"],
                "state":     scan["state"],
                "date":      scan["date"],
                "files":     [p.name for p in scan["pages"]],
                "ticket_id": scan["ticket_id"],
                "elapsed_s": round(elapsed, 1),
                **summ,
            }
            print(f"OK {elapsed:.1f}s  {summ['pass_status']:<7}"
                  f" conf={summ['avg_confidence']:.0%}"
                  f" [{summ['file_type']}]"
                  f" {summ['violation'][:25]}")
            done += 1
        except Exception as exc:
            elapsed = time.time() - t0
            results[scan["key"]] = {
                "status":    "error",
                "driver":    scan["driver"],
                "files":     [p.name for p in scan["pages"]],
                "error":     str(exc),
                "elapsed_s": round(elapsed, 1),
            }
            print(f"ERR {exc}")
            errors += 1

        with out_path.open("w") as fh:
            json.dump(results, fh, indent=2)

        if args.delay > 0 and i < total:
            time.sleep(args.delay)

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"Done: {done} scanned | {skipped} skipped (already done) | {errors} errors")

    ok  = [v for v in results.values() if v.get("status") == "ok"]
    if ok:
        avg_conf = sum(r.get("avg_confidence", 0) for r in ok) / len(ok)
        avg_time = sum(r.get("elapsed_s", 0) for r in ok) / len(ok)
        passes   = {"green": 0, "yellow": 0, "red": 0, "unknown": 0}
        for r in ok:
            passes[r.get("pass_status", "unknown")] = passes.get(r.get("pass_status", "unknown"), 0) + 1

        print(f"\nSummary ({len(ok)} scans):")
        print(f"  Avg confidence : {avg_conf:.1%}")
        print(f"  Avg scan time  : {avg_time:.1f}s")
        print(f"  Pass / Yellow / Red : {passes['green']} / {passes['yellow']} / {passes['red']}")

        low_conf = sorted(
            [(k, v) for k, v in results.items() if v.get("status") == "ok"],
            key=lambda x: x[1].get("avg_confidence", 1),
        )
        if low_conf:
            print(f"\nLowest confidence scans (review these):")
            for key, row in low_conf[:8]:
                print(f"  {row['driver'][:35]:<35} conf={row.get('avg_confidence', 0):.0%}"
                      f"  {row.get('pass_status','?'):<7}"
                      f"  lc={row.get('low_confidence_fields', [])[:2]}")

    print(f"\nResults saved to: {out_path}")
    print(f"Skipped {len(skip_log)} legal/non-scannable files (not posted)")


if __name__ == "__main__":
    main()
