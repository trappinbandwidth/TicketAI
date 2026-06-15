# CDL Legal — AI Ticket Scanner
## AWS Lightsail Deployment Guide

**Estimated time: 20–30 minutes**
**Requires: AWS account access, Anthropic API key**

---

## Step 1 — Create the Lightsail Instance

1. Go to [aws.amazon.com/lightsail](https://aws.amazon.com/lightsail) and sign in
2. Click **Create instance**
3. Select:
   - **Region:** US East (N. Virginia) — or whichever region CDL Legal uses
   - **Platform:** Linux/Unix
   - **Blueprint:** OS Only → **Ubuntu 22.04 LTS**
   - **Instance plan:** **$10/month** (2 GB RAM, 1 vCPU, 60 GB SSD) ← minimum recommended
4. Name it: `cdl-ticket-scanner`
5. Click **Create instance**
6. Wait ~60 seconds for status to show **Running**

---

## Step 2 — Open the Firewall

1. Click your new instance → **Networking** tab
2. Under **IPv4 Firewall**, click **Add rule**
3. Add: **HTTP — Port 80** → Save
4. *(Optional for SSL later)* Add: **HTTPS — Port 443** → Save

> Port 22 (SSH) is already open by default.

---

## Step 3 — SSH Into the Server

**Option A — Browser (easiest):**
On the instance page, click the **orange terminal icon** → "Connect using SSH"

**Option B — Your own terminal:**
1. Download the SSH key from Lightsail Account → SSH Keys
2. Run:
```bash
ssh -i ~/your-key.pem ubuntu@<YOUR-LIGHTSAIL-IP>
```

---

## Step 4 — Run the Setup Script

Once connected, run this single command:

```bash
curl -fsSL https://raw.githubusercontent.com/CDL-Legal/ai-ticket-engine/main/deploy/setup.sh | sudo bash
```

This will:
- Install Python 3.11, nginx, and dependencies
- Clone the repo to `/srv/cdl-ticket-scanner`
- Create a dedicated `cdlscanner` system user
- Install all Python packages into a virtual environment
- Register and start the API as a systemd service
- Configure nginx to serve the portal on port 80

**The script will pause and show this message:**
```
⚠  .env created at /srv/cdl-ticket-scanner/.env
⚠  Edit it now and fill in ANTHROPIC_API_KEY and API_KEY before continuing.
```

Proceed to Step 5 before the service will work.

---

## Step 5 — Set the Secret Keys

```bash
sudo nano /srv/cdl-ticket-scanner/.env
```

Fill in the following values:

```bash
ANTHROPIC_API_KEY=sk-ant-...        # Your Anthropic API key
API_KEY=choose-a-strong-secret      # Shared secret for the portal (make this something strong)
USE_MOCK=false

# Salesforce — required for attorney matching + case creation
SF_USERNAME=your-sf-username
SF_PASSWORD=your-sf-password
SF_SECURITY_TOKEN=your-sf-token
SF_DOMAIN=login
```

Save and exit: `Ctrl+O` → Enter → `Ctrl+X`

Then restart the service to load the new keys:
```bash
sudo systemctl restart cdl-ticket-scanner
```

---

## Step 6 — Verify It's Working

1. Open a browser and go to: `http://<YOUR-LIGHTSAIL-IP>`
2. You should see the CDL Legal portal
3. Enter your `API_KEY` in the API Key field in the header
4. Upload a test ticket — you should get a result in 15–30 seconds

**Check service health if anything is wrong:**
```bash
sudo systemctl status cdl-ticket-scanner
sudo journalctl -u cdl-ticket-scanner -n 50 --no-pager
```

---

## Step 7 — (Optional) Point a Domain

If CDL Legal has a domain (e.g. `tickets.cdllegal.com`):

1. In your DNS provider, add an **A record**:
   - Name: `tickets`
   - Value: `<YOUR-LIGHTSAIL-IP>`
2. In Lightsail, go to **Networking** → attach a **Static IP** to lock the IP address
3. For SSL (HTTPS), SSH back in and run:
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d tickets.cdllegal.com
```
Certbot auto-renews — nothing else needed.

---

## Future Code Updates

When new code is pushed to GitHub, deploy it with:

```bash
sudo bash /srv/cdl-ticket-scanner/deploy/update.sh
```

This pulls the latest code, updates dependencies, and restarts the service — takes about 30 seconds.

---

## Quick Reference

| What | Where |
|---|---|
| Portal URL | `http://<lightsail-ip>` |
| API docs | `http://<lightsail-ip>/docs` |
| App files | `/srv/cdl-ticket-scanner/` |
| Environment secrets | `/srv/cdl-ticket-scanner/.env` |
| SQLite database | `/srv/cdl-ticket-scanner/data/queue.db` |
| Training data | `/srv/cdl-ticket-scanner/training_data/` |
| Service logs | `sudo journalctl -u cdl-ticket-scanner -f` |
| Restart service | `sudo systemctl restart cdl-ticket-scanner` |
| Deploy update | `sudo bash /srv/cdl-ticket-scanner/deploy/update.sh` |

---

## Monthly Cost Estimate

| Resource | Cost |
|---|---|
| Lightsail $10/mo instance | $10.00 |
| Lightsail Static IP (if attached to running instance) | $0.00 |
| Data transfer (generous free tier) | $0.00 |
| **Total infrastructure** | **~$10/mo** |

> Anthropic API usage (Claude Sonnet) is billed separately per scan — approximately $0.02–$0.06 per ticket depending on complexity.

---

*CDL Legal — Internal Use Only*
*github.com/CDL-Legal/ai-ticket-engine*
