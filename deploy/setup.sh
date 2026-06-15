#!/usr/bin/env bash
# CDL Legal — AI Ticket Scanner
# One-time server setup for AWS Lightsail (Ubuntu 22.04)
# Run as: sudo bash setup.sh

set -euo pipefail

APP_DIR="/srv/cdl-ticket-scanner"
APP_USER="cdlscanner"
REPO="https://github.com/CDL-Legal/ai-ticket-engine.git"

echo "── [1/8] System packages ──────────────────────────────────"
apt-get update -q
apt-get install -y -q python3.11 python3.11-venv python3-pip nginx git curl

echo "── [2/8] Create app user ───────────────────────────────────"
id "$APP_USER" &>/dev/null || useradd --system --no-create-home --shell /bin/false "$APP_USER"

echo "── [3/8] Clone repo ────────────────────────────────────────"
mkdir -p "$APP_DIR"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull
else
  git clone "$REPO" "$APP_DIR"
fi
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

echo "── [4/8] Python venv + dependencies ───────────────────────"
python3.11 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

echo "── [5/8] Data directories ──────────────────────────────────"
mkdir -p "$APP_DIR/data" "$APP_DIR/training_data"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR/data" "$APP_DIR/training_data"

echo "── [6/8] Environment file ──────────────────────────────────"
if [ ! -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env" 2>/dev/null || cat > "$APP_DIR/.env" <<'EOF'
# CDL Ticket Scanner — Production Environment
# Fill in ALL values before starting the service

ANTHROPIC_API_KEY=sk-ant-...
API_KEY=change-me-in-production
USE_MOCK=false

# Salesforce (optional — attorney matching + case creation)
SF_USERNAME=
SF_PASSWORD=
SF_SECURITY_TOKEN=
SF_DOMAIN=login
EOF
  chown "$APP_USER":"$APP_USER" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  echo ""
  echo "  ⚠  .env created at $APP_DIR/.env"
  echo "  ⚠  Edit it now and fill in ANTHROPIC_API_KEY and API_KEY before continuing."
  echo ""
fi

echo "── [7/8] systemd service ───────────────────────────────────"
cp "$APP_DIR/deploy/cdl-ticket-scanner.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable cdl-ticket-scanner
systemctl restart cdl-ticket-scanner
systemctl status cdl-ticket-scanner --no-pager

echo "── [8/8] nginx ─────────────────────────────────────────────"
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/cdl-ticket-scanner
ln -sf /etc/nginx/sites-available/cdl-ticket-scanner /etc/nginx/sites-enabled/cdl-ticket-scanner
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo ""
echo "✅  Setup complete."
echo "    Portal:  http://$(curl -s ifconfig.me)"
echo "    API:     http://$(curl -s ifconfig.me)/api/v1/docs"
echo ""
echo "    Next: open Lightsail firewall for port 80 (and 443 if adding SSL)."
