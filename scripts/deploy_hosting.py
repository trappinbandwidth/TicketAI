#!/usr/bin/env python3
"""
Deploy a directory to Firebase Hosting via REST API.
Bypasses the Firebase CLI (which requires an interactive login).

Usage:
  python3 deploy_hosting.py <site_id> <dist_dir> <firebase_json>

Example:
  python3 deploy_hosting.py rigresolve-admin frontend-qa/dist frontend-qa/firebase.json
"""

import gzip
import hashlib
import io
import json
import mimetypes
import os
import ssl
import subprocess
import sys
import urllib.request

import requests as _requests

HOSTING_API = "https://firebasehosting.googleapis.com/v1beta1"


def get_token():
    result = subprocess.run(
        ["gcloud", "auth", "print-access-token", "--quiet"],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "x-goog-user-project": "rigresolve",
    }


def ctx():
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c


def api(method, path, body=None, token=None, extra_headers=None):
    url = f"{HOSTING_API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    h = headers(token)
    if extra_headers:
        h.update(extra_headers)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, context=ctx()) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read()
        print(f"HTTP {e.code}: {body.decode()}")
        raise


def gzip_bytes(data: bytes) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        gz.write(data)
    return buf.getvalue()


def sha256_hex(path: str) -> str:
    with open(path, "rb") as f:
        raw = f.read()
    compressed = gzip_bytes(raw)
    return hashlib.sha256(compressed).hexdigest()


def upload_file(upload_url, file_path, token):
    mime = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    with open(file_path, "rb") as f:
        raw = f.read()
    compressed = gzip_bytes(raw)
    resp = _requests.post(
        upload_url,
        data=compressed,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": mime,
        },
        verify=False,
    )
    if not resp.ok:
        print(f"  Upload HTTP {resp.status_code}: {resp.text}")
        resp.raise_for_status()


def collect_files(dist_dir):
    files = {}
    for root, _, names in os.walk(dist_dir):
        for name in names:
            abs_path = os.path.join(root, name)
            rel = "/" + os.path.relpath(abs_path, dist_dir).replace(os.sep, "/")
            files[rel] = abs_path
    return files


def main(site_id, dist_dir, firebase_json_path):
    token = get_token()

    # Load firebase.json config for rewrites/headers
    with open(firebase_json_path) as f:
        config = json.load(f)
    hosting_config = config.get("hosting", {})

    # Translate firebase.json format → REST API format
    # firebase.json uses "source" key; REST API uses "glob"
    rewrites = []
    for r in hosting_config.get("rewrites", []):
        entry = {k: v for k, v in r.items()}
        if "source" in entry:
            entry["glob"] = entry.pop("source")
        if "destination" in entry:
            entry["path"] = entry.pop("destination")
        rewrites.append(entry)

    # headers: firebase.json uses [{source, headers:[{key,value}]}]
    # REST API uses [{glob, headers:{key:value}}]
    headers_list = []
    for h in hosting_config.get("headers", []):
        glob = h.get("source", h.get("glob", "**"))
        hdr_map = {}
        for item in h.get("headers", []):
            hdr_map[item["key"]] = item["value"]
        headers_list.append({"glob": glob, "headers": hdr_map})

    version_config = {"rewrites": rewrites}
    if headers_list:
        version_config["headers"] = headers_list

    print(f"[1/5] Creating version on site '{site_id}'...")
    version = api("POST", f"/sites/{site_id}/versions", body={"config": version_config}, token=token)
    version_name = version["name"]
    version_id = version_name.split("/")[-1]
    print(f"      version: {version_id}")

    print("[2/5] Collecting dist files and computing hashes...")
    files = collect_files(dist_dir)
    file_hashes = {rel: sha256_hex(abs_path) for rel, abs_path in files.items()}
    print(f"      {len(files)} files")

    print("[3/5] Requesting upload URLs...")
    populate_body = {"files": {rel: h for rel, h in file_hashes.items()}}
    populate_resp = api(
        "POST",
        f"/sites/{site_id}/versions/{version_id}:populateFiles",
        body=populate_body,
        token=token,
    )
    upload_required = populate_resp.get("uploadRequiredHashes", [])
    upload_url_base = populate_resp.get("uploadUrl", "")
    print(f"      {len(upload_required)} files need uploading (rest already cached)")

    print("[4/5] Uploading files...")
    hash_to_rel = {v: k for k, v in file_hashes.items()}
    for file_hash in upload_required:
        rel = hash_to_rel.get(file_hash, "?")
        abs_path = files.get(rel, "")
        print(f"      -> {rel}")
        upload_url = f"{upload_url_base}/{file_hash}"
        upload_file(upload_url, abs_path, token)

    print("[5/5] Finalizing version and creating release...")
    api(
        "PATCH",
        f"/sites/{site_id}/versions/{version_id}?update_mask=status",
        body={"status": "FINALIZED"},
        token=token,
    )
    release = api(
        "POST",
        f"/sites/{site_id}/releases?versionName={version_name}",
        token=token,
    )
    print(f"\nDone! Release: {release.get('name')}")
    print(f"Live at: https://{site_id}.web.app")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
