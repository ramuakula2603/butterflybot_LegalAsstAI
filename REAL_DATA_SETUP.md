# Real Data Setup (Andhra Pradesh + Telangana)

This project now reads legal statutes and precedents from PostgreSQL (not JSON mock files).

## Supported states
- `andhra pradesh`
- `telangana`
- shared national entries can be loaded with `all`

## 1) CSV format
Use these template headers:
- `data/templates/statutes_template.csv`
- `data/templates/precedents_template.csv`

### Statutes CSV columns
- `state`
- `legacy_code`
- `legacy_section`
- `new_code`
- `new_section`
- `title`
- `keywords` (pipe-separated, e.g. `anticipatory bail|pre-arrest bail`)
- `source_url`

### Precedents CSV columns
- `state`
- `title`
- `citation`
- `court`
- `year`
- `topics` (pipe-separated)
- `snippet`
- `source_url`

## 2) Ingest data
Start API, then upload CSV files:

```powershell
curl.exe -s -X POST -F "file=@C:\path\to\statutes.csv" http://127.0.0.1:8000/api/v1/admin/ingest/statutes
curl.exe -s -X POST -F "file=@C:\path\to\precedents.csv" http://127.0.0.1:8000/api/v1/admin/ingest/precedents
```

## 3) Check corpus status

```powershell
curl.exe -s http://127.0.0.1:8000/api/v1/admin/corpus/status
```

## 4) Query with state scope
Send `state` as `telangana` or `andhra pradesh`.

## 5) No local data? Ingest from public URLs
You can ingest public legal pages directly:

```powershell
$body = @{
	state = "telangana"
	document_type = "precedent"
	urls = @(
		"https://indiankanoon.org/doc/1033637/",
		"https://indiankanoon.org/doc/101371569/"
	)
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/admin/ingest/public-urls -ContentType "application/json" -Body $body
```

This stores extracted snippets with source URLs in your PostgreSQL corpus.

## 6) Optional LLM fallback
If corpus retrieval is empty, API can include `llm_fallback` output when `OPENAI_API_KEY` is set.

## 7) Daily scheduled refresh (non-disruptive)
The app supports automatic daily public-source refresh in background without interrupting API usage.

### Default schedule
- Daily at `02:15` Asia/Kolkata

### Env config
- `DAILY_REFRESH_ENABLED=true`
- `DAILY_REFRESH_HOUR=2`
- `DAILY_REFRESH_MINUTE=15`
- `PUBLIC_SOURCES_FILE=data/public_sources.json`
- `ALERT_ON_FAILURE=false`
- `ALERT_WEBHOOK_URL=`

### Source list file
Edit `data/public_sources.json` with AP/Telangana URL lists.

### Monitor and trigger
```powershell
curl.exe -s http://127.0.0.1:8000/api/v1/admin/scheduler/status
curl.exe -s -X POST http://127.0.0.1:8000/api/v1/admin/scheduler/run-once
curl.exe -s "http://127.0.0.1:8000/api/v1/admin/scheduler/runs?limit=20"
```

Refresh is upsert-only (no destructive wipe), so existing details are preserved.
Each run is saved in an audit log table with started/ended time, inserted count, and failed URLs.

## Data quality note
Use authoritative sources only and retain `source_url` for audit/citation traceability.
