# ButterflyBot Legal Assistant (AP/TS)

Production-focused legal assistant for Andhra Pradesh and Telangana with real-data ingestion, strict source filtering, instant legal guidance, drafting support, and operational quality monitoring.

## What this includes

- FastAPI backend with UI at `/ui`
- Legal analysis endpoints with:
  - section mapping
  - precedent/citation retrieval
  - district playbooks (Hyderabad, Rangareddy, Vijayawada, Visakhapatnam)
  - filing templates + copy-ready draft text
- Instant Solve endpoint (`/api/v1/legal/instant-solve`) with auto-inference
- FIR analysis (txt/docx/pdf/image OCR)
- Case history CRUD
- Scheduler for daily source refresh
- Data Quality Dashboard (`/api/v1/admin/data-quality`)

## Real-data and production safeguards

- Supported states are strictly:
  - `telangana`
  - `andhra pradesh`
- Public ingestion accepts only trusted legal domains.
- Low-quality/placeholder records are filtered (e.g., untitled/not-found pages).
- Dashboard metrics expose data trust and quality coverage.

## Local run

1. Create/activate virtual environment
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create env file from template:

```bash
cp .env.example .env
```

4. Ensure PostgreSQL is running and env vars are set (or use defaults used by this project):

- `POSTGRES_HOST` (default `127.0.0.1`)
- `POSTGRES_PORT` (default `5432`)
- `POSTGRES_DB` (default `postgres`)
- `POSTGRES_USER` (default `postgres`)
- `POSTGRES_PASSWORD` (default `pass`)

5. Start API:

```bash
uvicorn main:app --host 127.0.0.1 --port 8001
```

Alternative setup helper (Linux):

```bash
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

## Access URLs

- UI: `http://127.0.0.1:8001/ui`
- Health: `http://127.0.0.1:8001/health`
- Data quality: `http://127.0.0.1:8001/api/v1/admin/data-quality`

## Key endpoints

- `POST /api/v1/legal/question`
- `POST /api/v1/legal/instant-solve`
- `POST /api/v1/fir/analyze`
- `POST /api/v1/precedents/search`
- `GET|POST|PUT|DELETE /api/v1/cases`
- `GET /api/v1/admin/corpus/status`
- `POST /api/v1/admin/ingest/statutes`
- `POST /api/v1/admin/ingest/precedents`
- `POST /api/v1/admin/ingest/public-urls`
- `GET /api/v1/admin/scheduler/status`
- `POST /api/v1/admin/scheduler/run-once`
- `GET /api/v1/admin/scheduler/runs`
- `GET /api/v1/admin/data-quality`

## Notes

- Keep API on `8001` if `8000` is occupied on your machine.
- See `REAL_DATA_SETUP.md` for corpus setup guidance.
