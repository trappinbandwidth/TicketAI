#!/usr/bin/env bash
# CDL Legal — AI Ticket Scanner
# Deploy latest code from GitHub.
# Run as: sudo bash update.sh

set -euo pipefail

APP_DIR="/srv/cdl-ticket-scanner"
APP_USER="cdlscanner"

echo "── Pulling latest code ─────────────────────────────────────"
git -C "$APP_DIR" pull

echo "── Updating dependencies ───────────────────────────────────"
"$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

echo "── Restarting service ──────────────────────────────────────"
systemctl restart cdl-ticket-scanner
sleep 2
systemctl status cdl-ticket-scanner --no-pager

echo "── Reloading nginx ─────────────────────────────────────────"
nginx -t && systemctl reload nginx

echo ""
echo "✅  Update complete — $(git -C "$APP_DIR" log --oneline -1)"
