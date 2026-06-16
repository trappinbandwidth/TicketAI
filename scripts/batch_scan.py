#!/usr/bin/env python3
"""
Batch-scan ticket images through the AI engine API.

Usage:
  python scripts/batch_scan.py [--dir PATH] [--api URL] [--out FILE] [--limit N]

Defaults:
  --dir   ~/claude_tmp/ticket_images   (PNG/JPG files)
  --api   http://localhost:8000
  --out   scripts/batch_results.json
  --limit 0 (all)

Results are saved incrementally so a restart won't re-run completed images.
"""

import argparse, json, os, sys, time
from pathlib import Path

import requests

DEFAULT_IMAGE_DIR = Path.home() / "claude_tmp" / "ticket_images"
DEFAULT_API       = "http://127.0.0.1:8000"
DEFAULT_OUT       = Path(__file__).parent / "batch_results.json"
API_KEY           = os.getenv("API_KEY", "cdl-local-dev")
HEADERS           = {"X-API-Key": API_KEY}


def scan_image(api_base: str, image_path: Path) -> dict:
    url = f"{api_base}/api/v1/process"
    mime = "image/jpeg" if image_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    with image_path.open("rb") as f:
        files = [("files", (image_path.name, f, mime))]
        resp = requests.post(url, headers=HEADERS, files=files, timeout=300)
    resp.raise_for_status()
    return resp.json()


def main():
    p = argparse.ArgumentParser(description="Batch ticket scanner")
    p.add_argument("--dir",   default=str(DEFAULT_IMAGE_DIR))
    p.add_argument("--api",   default=DEFAULT_API)
    p.add_argument("--out",   default=str(DEFAULT_OUT))
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()

    image_dir = Path(args.dir)
    out_path  = Path(args.out)

    images = sorted(
        [f for f in image_dir.iterdir() if f.suffix.lower() in (".png", ".jpg", ".jpeg")]
    )
    if args.limit:
        images = images[: args.limit]

    # Load existing results to allow resume
    results = {}
    if out_path.exists():
        with out_path.open() as f:
            results = json.load(f)
        print(f"Resuming — {len(results)} already done")

    total = len(images)
    print(f"Scanning {total} images from {image_dir}")
    print(f"API: {args.api}  |  Output: {out_path}")
    print()

    done = skipped = errors = 0
    for i, img in enumerate(images, 1):
        key = img.name
        if key in results:
            skipped += 1
            continue

        print(f"[{i:3d}/{total}] {img.name} ...", end=" ", flush=True)
        t0 = time.time()
        try:
            data = scan_image(args.api, img)
            elapsed = time.time() - t0

            # Fields live inside data["result"] as ExtractedField objects
            result_obj = data.get("result") or {}
            fields = {
                k: v for k, v in result_obj.items()
                if isinstance(v, dict) and "confidence_score" in v
            }
            # Exclude "Not applicable" N/A fields (value="" and score=0) from avg
            applicable = {k: v for k, v in fields.items() if v.get("value") or v["confidence_score"] > 0}
            scores   = [v["confidence_score"] for v in applicable.values()]
            avg_conf = sum(scores) / len(scores) if scores else 0.0
            filled   = sum(1 for v in applicable.values() if v.get("value"))

            results[key] = {
                "status":               "ok",
                "elapsed_s":            round(elapsed, 1),
                "queue_id":             data.get("queue_id"),
                "pass_status":          data.get("pass_status"),
                "avg_field_confidence": round(avg_conf, 3),
                "fields_filled":        filled,
                "total_fields":         len(fields),
                "low_confidence_fields": data.get("low_confidence_fields", []),
                "data":                 data,
            }
            print(f"OK  {elapsed:.1f}s  {data.get('pass_status','?'):<6}  conf={avg_conf:.0%}  {filled}/{len(fields)} fields")
            done += 1
        except Exception as exc:
            elapsed = time.time() - t0
            results[key] = {"status": "error", "error": str(exc), "elapsed_s": round(elapsed, 1)}
            print(f"ERR {exc}")
            errors += 1

        # Save after every image
        with out_path.open("w") as f:
            json.dump(results, f, indent=2)

    print()
    print(f"Done: {done} scanned, {skipped} skipped, {errors} errors")

    # Summary table
    ok_rows = [v for v in results.values() if v["status"] == "ok"]
    if ok_rows:
        avg_conf   = sum(r["avg_field_confidence"] for r in ok_rows) / len(ok_rows)
        avg_filled = sum(r["fields_filled"] for r in ok_rows) / len(ok_rows)
        avg_time   = sum(r["elapsed_s"] for r in ok_rows) / len(ok_rows)
        print(f"\nSummary ({len(ok_rows)} scans):")
        print(f"  Avg confidence : {avg_conf:.1%}")
        print(f"  Avg fields filled: {avg_filled:.1f}")
        print(f"  Avg scan time  : {avg_time:.1f}s")

        print("\nLowest confidence scans:")
        sorted_ok = sorted(
            [(k, v) for k, v in results.items() if v["status"] == "ok"],
            key=lambda x: x[1]["avg_field_confidence"],
        )
        for fname, row in sorted_ok[:5]:
            print(f"  {fname:<30}  conf={row['avg_field_confidence']:.1%}  fields={row['fields_filled']}/{row['total_fields']}")


if __name__ == "__main__":
    main()
