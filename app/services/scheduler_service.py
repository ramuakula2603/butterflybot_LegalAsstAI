import json
import os
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .alert_service import AlertService
from .legal_data_service import LegalDataService
from .public_ingestion_service import PublicIngestionService


class DailyRefreshScheduler:
    def __init__(self, legal_data_service: LegalDataService, ingestion_service: PublicIngestionService) -> None:
        self.legal_data_service = legal_data_service
        self.ingestion_service = ingestion_service
        self.scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
        self.enabled = os.getenv("DAILY_REFRESH_ENABLED", "true").strip().lower() == "true"
        self.hour = int(os.getenv("DAILY_REFRESH_HOUR", "2"))
        self.minute = int(os.getenv("DAILY_REFRESH_MINUTE", "15"))
        self.sources_file = Path(os.getenv("PUBLIC_SOURCES_FILE", "data/public_sources.json"))
        self.alert_service = AlertService()

        self.last_run_id: int | None = None
        self.last_run_at: str | None = None
        self.last_inserted: int = 0
        self.last_failed_urls: list[str] = []

    def _load_sources(self) -> list[dict]:
        if not self.sources_file.is_absolute():
            base = Path(__file__).resolve().parents[2]
            path = base / self.sources_file
        else:
            path = self.sources_file

        if not path.exists():
            return []

        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
            return payload.get("sources", [])

    def run_once(self) -> dict:
        run_id = self.legal_data_service.create_scheduler_run()
        self.last_run_id = run_id

        sources = self._load_sources()
        total_inserted = 0
        failed_urls: list[str] = []
        urls_attempted = 0

        try:
            for source in sources:
                state = (source.get("state") or "").strip().lower()
                urls = source.get("urls") or []
                if state not in {"andhra pradesh", "telangana"}:
                    continue

                urls_attempted += len(urls)
                parsed, failed = self.ingestion_service.parse_urls(urls)
                records = [
                    {
                        "state": state,
                        "title": item["title"],
                        "citation": item["source_url"],
                        "court": "Public Source",
                        "year": None,
                        "topics": ["public-source", state],
                        "snippet": item["snippet"],
                        "source_url": item["source_url"],
                    }
                    for item in parsed
                ]
                total_inserted += self.legal_data_service.upsert_precedent_records(records)
                failed_urls.extend(failed)

            self.last_run_at = datetime.now(timezone.utc).isoformat()
            self.last_inserted = total_inserted
            self.last_failed_urls = failed_urls

            final_status = "failed" if failed_urls else "success"
            self.legal_data_service.finalize_scheduler_run(
                run_id=run_id,
                status=final_status,
                sources_processed=len(sources),
                urls_attempted=urls_attempted,
                inserted_count=total_inserted,
                failed_urls=failed_urls,
            )
            self.legal_data_service.data_quality_summary(
                capture_snapshot=True,
                source="scheduler_run",
                run_id=run_id,
            )

            if failed_urls:
                self.alert_service.send_failure_alert(
                    message="ButterflyBot daily refresh completed with URL failures",
                    details={
                        "run_id": run_id,
                        "failed_urls": failed_urls,
                        "inserted": total_inserted,
                    },
                )

            return {
                "run_id": run_id,
                "inserted": total_inserted,
                "failed_urls": failed_urls,
                "sources_processed": len(sources),
                "urls_attempted": urls_attempted,
            }
        except Exception as exc:
            self.last_run_at = datetime.now(timezone.utc).isoformat()
            self.last_inserted = total_inserted
            self.last_failed_urls = failed_urls
            self.legal_data_service.finalize_scheduler_run(
                run_id=run_id,
                status="error",
                sources_processed=len(sources),
                urls_attempted=urls_attempted,
                inserted_count=total_inserted,
                failed_urls=failed_urls,
                error_message=str(exc),
            )
            self.legal_data_service.data_quality_summary(
                capture_snapshot=True,
                source="scheduler_error",
                run_id=run_id,
            )

            self.alert_service.send_failure_alert(
                message="ButterflyBot daily refresh failed",
                details={"run_id": run_id, "error": str(exc)},
            )
            raise

    def start(self) -> None:
        if not self.enabled:
            return

        if self.scheduler.running:
            return

        trigger = CronTrigger(hour=self.hour, minute=self.minute)
        self.scheduler.add_job(
            self.run_once,
            trigger=trigger,
            id="daily_public_refresh",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        self.scheduler.start()

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def status(self) -> dict:
        return {
            "enabled": self.enabled,
            "running": self.scheduler.running,
            "schedule": f"daily {self.hour:02d}:{self.minute:02d} Asia/Kolkata",
            "last_run_id": self.last_run_id,
            "last_run_at": self.last_run_at,
            "last_inserted": self.last_inserted,
            "last_failed_urls": self.last_failed_urls,
        }
