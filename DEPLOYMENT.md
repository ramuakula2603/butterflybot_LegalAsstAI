# Deployment Runbook (ButterflyBot Legal Assistant)

This document covers production deployment and operations for the AP/TS legal assistant.

## 1) Infrastructure baseline

- OS: Linux VM or container host
- Python: 3.11+
- PostgreSQL: 14+
- Reverse proxy: Nginx/Caddy
- Process manager: systemd / supervisor / container orchestrator

## 2) Required environment variables

Set these before starting API:

- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `OPENAI_API_KEY` (optional fallback mode)
- `LEGAL_LLM_MODEL` (optional)
- `ALERT_WEBHOOK_URL` (optional alerts)

## 3) Initial setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run once to initialize DB schema via application startup.

## 4) Start command

```bash
uvicorn main:app --host 0.0.0.0 --port 8001
```

Recommended production command:

```bash
gunicorn -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:8001 main:app
```

Ready templates are included in the repo:

- `deploy/systemd/butterflybot.service`
- `deploy/nginx/butterflybot.conf`

Update paths/domain before use.

## 5) Reverse proxy

Route HTTPS traffic to `127.0.0.1:8001`.

Expose:

- `/ui`
- `/health`
- `/api/v1/*`

Restrict admin endpoints (`/api/v1/admin/*`) by IP or auth layer at proxy.

### systemd setup

```bash
sudo cp deploy/systemd/butterflybot.service /etc/systemd/system/butterflybot.service
sudo systemctl daemon-reload
sudo systemctl enable butterflybot
sudo systemctl start butterflybot
sudo systemctl status butterflybot
```

### nginx setup

```bash
sudo cp deploy/nginx/butterflybot.conf /etc/nginx/sites-available/butterflybot.conf
sudo ln -s /etc/nginx/sites-available/butterflybot.conf /etc/nginx/sites-enabled/butterflybot.conf
sudo nginx -t
sudo systemctl reload nginx
```

## 6) Data quality guardrails

- Ingest only trusted legal domains.
- Reject low-quality placeholder pages.
- Monitor:
  - `GET /api/v1/admin/data-quality`
  - `GET /api/v1/admin/scheduler/status`
  - `GET /api/v1/admin/scheduler/runs`

Minimum acceptance targets:

- `trusted_source_pct >= 95`
- `high_quality_pct >= 80`
- scheduler URL failures near zero

## 7) Scheduler operations

- Daily refresh runs automatically at configured schedule.
- Manual trigger:

```bash
POST /api/v1/admin/scheduler/run-once
```

If failures spike:

1. Check `/api/v1/admin/scheduler/runs`
2. Remove broken source URLs
3. Re-run once and verify insert counts

## 8) Backup and recovery

- PostgreSQL daily backups (`pg_dump`) + weekly restore drill.
- Keep at least 14 backup points.
- Validate recovery by restoring to staging and running `/health` + `/api/v1/admin/data-quality`.

## 9) Smoke test checklist after deploy

- `GET /health` returns healthy
- `/ui` loads
- `POST /api/v1/legal/instant-solve` works for AP and TS
- `GET /api/v1/admin/data-quality` returns metrics

## 10) Security checklist

- Enforce HTTPS
- Restrict admin routes
- Rotate DB and API keys
- Do not expose `.env`
- Limit CORS origins in production

## 11) Recommended next hardening

- Add admin auth for all `/api/v1/admin/*`
- Add request rate limits
- Add structured application logging
- Add uptime alerting for `/health`
