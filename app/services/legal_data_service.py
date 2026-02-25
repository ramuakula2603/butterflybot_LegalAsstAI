import csv
import os
import re
from contextlib import contextmanager
from io import StringIO
from typing import Iterator
from urllib.parse import urlparse

import psycopg2
from psycopg2.extras import RealDictCursor

SUPPORTED_STATES = {"andhra pradesh", "telangana", "all"}
TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")
TRUSTED_SOURCE_DOMAINS = {
    "indiankanoon.org",
    "indiacode.nic.in",
    "sci.gov.in",
    "tshc.gov.in",
    "hc.ap.nic.in",
    "districts.ecourts.gov.in",
}


class LegalDataService:
    def __init__(self) -> None:
        self.host = os.getenv("POSTGRES_HOST", "127.0.0.1")
        self.port = int(os.getenv("POSTGRES_PORT", "5432"))
        self.database = os.getenv("POSTGRES_DB", "postgres")
        self.user = os.getenv("POSTGRES_USER", "postgres")
        self.password = os.getenv("POSTGRES_PASSWORD", "pass")

    @contextmanager
    def _connect(self) -> Iterator[psycopg2.extensions.connection]:
        connection = psycopg2.connect(
            host=self.host,
            port=self.port,
            dbname=self.database,
            user=self.user,
            password=self.password,
        )
        try:
            yield connection
        finally:
            connection.close()

    def _tokenize(self, text: str) -> set[str]:
        return {token.lower() for token in TOKEN_PATTERN.findall(text) if len(token) > 2}

    def _is_trusted_source(self, url: str | None) -> bool:
        if not url:
            return False
        try:
            host = (urlparse(url).hostname or "").lower()
        except Exception:
            return False
        if not host:
            return False
        return any(host == domain or host.endswith(f".{domain}") for domain in TRUSTED_SOURCE_DOMAINS)

    def _is_high_quality_precedent_row(
        self,
        *,
        title: str,
        snippet: str,
        citation: str,
        source_url: str | None,
    ) -> bool:
        normalized_title = (title or "").strip().lower()
        normalized_snippet = (snippet or "").strip()
        normalized_citation = (citation or "").strip()

        if not normalized_title or normalized_title in {"untitled", "unknown"}:
            return False
        if len(normalized_snippet) < 120:
            return False
        lowered = normalized_snippet.lower()
        if "act/judgment not found" in lowered or "document not found" in lowered:
            return False
        if not normalized_citation:
            return False
        if not self._is_trusted_source(source_url):
            return False
        return True

    def init_schema(self) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS statute_reference (
                id SERIAL PRIMARY KEY,
                state TEXT NOT NULL,
                legacy_code TEXT NOT NULL,
                legacy_section TEXT NOT NULL,
                new_code TEXT NOT NULL,
                new_section TEXT NOT NULL,
                title TEXT NOT NULL,
                keywords TEXT[] NOT NULL DEFAULT '{}',
                source_url TEXT,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (state, legacy_code, legacy_section, new_code, new_section)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS precedent_corpus (
                id SERIAL PRIMARY KEY,
                state TEXT NOT NULL,
                title TEXT NOT NULL,
                citation TEXT NOT NULL,
                court TEXT NOT NULL,
                year INT,
                topics TEXT[] NOT NULL DEFAULT '{}',
                snippet TEXT NOT NULL,
                source_url TEXT,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (state, citation)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS scheduler_run_audit (
                id SERIAL PRIMARY KEY,
                started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                ended_at TIMESTAMPTZ,
                status TEXT NOT NULL,
                sources_processed INT NOT NULL DEFAULT 0,
                urls_attempted INT NOT NULL DEFAULT 0,
                inserted_count INT NOT NULL DEFAULT 0,
                failed_count INT NOT NULL DEFAULT 0,
                failed_urls TEXT[] NOT NULL DEFAULT '{}',
                error_message TEXT
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS data_quality_history (
                id SERIAL PRIMARY KEY,
                captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                source TEXT NOT NULL,
                run_id INT,
                total_precedent_records INT NOT NULL DEFAULT 0,
                trusted_source_records INT NOT NULL DEFAULT 0,
                high_quality_records INT NOT NULL DEFAULT 0,
                rejected_or_low_quality_records INT NOT NULL DEFAULT 0,
                trusted_source_pct NUMERIC(6, 2) NOT NULL DEFAULT 0,
                high_quality_pct NUMERIC(6, 2) NOT NULL DEFAULT 0,
                scheduler_urls_attempted INT NOT NULL DEFAULT 0,
                scheduler_records_inserted INT NOT NULL DEFAULT 0,
                scheduler_url_failures INT NOT NULL DEFAULT 0
            );
            """,
        ]

        with self._connect() as connection:
            with connection.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)
                connection.commit()

    def corpus_counts(self) -> dict:
        with self._connect() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT state, COUNT(*)::int AS count FROM statute_reference GROUP BY state ORDER BY state;")
                statutes = [dict(row) for row in cursor.fetchall()]
                cursor.execute("SELECT state, COUNT(*)::int AS count FROM precedent_corpus GROUP BY state ORDER BY state;")
                precedents = [dict(row) for row in cursor.fetchall()]
                return {"statutes": statutes, "precedents": precedents}

    def load_statutes_csv(self, csv_text: str) -> int:
        cleaned = csv_text.lstrip("\ufeff").strip()
        reader = csv.DictReader(StringIO(cleaned))
        rows = list(reader)
        if not rows:
            return 0

        sql = """
        INSERT INTO statute_reference
        (state, legacy_code, legacy_section, new_code, new_section, title, keywords, source_url)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (state, legacy_code, legacy_section, new_code, new_section)
        DO UPDATE SET title = EXCLUDED.title, keywords = EXCLUDED.keywords, source_url = EXCLUDED.source_url, updated_at = NOW();
        """

        inserted = 0
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for row in rows:
                    state = (row.get("state") or "").strip().lower()
                    if state not in SUPPORTED_STATES:
                        continue
                    keywords = [item.strip() for item in (row.get("keywords") or "").split("|") if item.strip()]
                    cursor.execute(
                        sql,
                        (
                            state,
                            (row.get("legacy_code") or "").strip(),
                            (row.get("legacy_section") or "").strip(),
                            (row.get("new_code") or "").strip(),
                            (row.get("new_section") or "").strip(),
                            (row.get("title") or "").strip(),
                            keywords,
                            (row.get("source_url") or "").strip() or None,
                        ),
                    )
                    inserted += 1
                connection.commit()
        return inserted

    def load_precedents_csv(self, csv_text: str) -> int:
        cleaned = csv_text.lstrip("\ufeff").strip()
        reader = csv.DictReader(StringIO(cleaned))
        rows = list(reader)
        if not rows:
            return 0

        sql = """
        INSERT INTO precedent_corpus
        (state, title, citation, court, year, topics, snippet, source_url)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (state, citation)
        DO UPDATE SET
            title = EXCLUDED.title,
            court = EXCLUDED.court,
            year = EXCLUDED.year,
            topics = EXCLUDED.topics,
            snippet = EXCLUDED.snippet,
            source_url = EXCLUDED.source_url,
            updated_at = NOW();
        """

        inserted = 0
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for row in rows:
                    state = (row.get("state") or "").strip().lower()
                    if state not in SUPPORTED_STATES:
                        continue
                    topics = [item.strip() for item in (row.get("topics") or "").split("|") if item.strip()]
                    year_value = (row.get("year") or "").strip()
                    year = int(year_value) if year_value.isdigit() else None

                    title = (row.get("title") or "").strip()
                    citation = (row.get("citation") or "").strip()
                    snippet = (row.get("snippet") or "").strip()
                    source_url = (row.get("source_url") or "").strip() or None
                    if not self._is_high_quality_precedent_row(
                        title=title,
                        snippet=snippet,
                        citation=citation,
                        source_url=source_url,
                    ):
                        continue

                    cursor.execute(
                        sql,
                        (
                            state,
                            title,
                            citation,
                            (row.get("court") or "").strip(),
                            year,
                            topics,
                            snippet,
                            source_url,
                        ),
                    )
                    inserted += 1
                connection.commit()
        return inserted

    def fetch_statute_matches(self, text: str, state: str, limit: int = 10) -> list[dict]:
        query = """
        SELECT state, legacy_code, legacy_section, new_code, new_section, title, keywords, source_url
        FROM statute_reference
        WHERE (state = %s OR state = 'all')
        ORDER BY CASE WHEN state = %s THEN 0 ELSE 1 END, updated_at DESC;
        """

        query_tokens = self._tokenize(text)
        scored: list[tuple[float, dict]] = []

        with self._connect() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, (state, state))
                rows = [dict(row) for row in cursor.fetchall()]

        for row in rows:
            if not self._is_high_quality_precedent_row(
                title=row.get("title", ""),
                snippet=row.get("snippet", ""),
                citation=row.get("citation", ""),
                source_url=row.get("source_url"),
            ):
                continue

            searchable = " ".join(
                [
                    row.get("title", ""),
                    f"{row.get('legacy_code', '')} {row.get('legacy_section', '')}",
                    f"{row.get('new_code', '')} {row.get('new_section', '')}",
                    " ".join(row.get("keywords", [])),
                ]
            )
            tokens = self._tokenize(searchable)
            overlap = query_tokens.intersection(tokens)
            score = len(overlap) / max(len(query_tokens), 1) if query_tokens else 0.0
            if score > 0:
                scored.append((score, row))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [row for _, row in scored[:limit]]

    def fetch_precedent_matches(self, query_text: str, state: str, limit: int = 5) -> list[dict]:
        query = """
        SELECT state, title, citation, court, year, topics, snippet, source_url
        FROM precedent_corpus
        WHERE (state = %s OR state = 'all')
        ORDER BY CASE WHEN state = %s THEN 0 ELSE 1 END, year DESC NULLS LAST;
        """

        query_tokens = self._tokenize(query_text)
        scored: list[tuple[float, dict]] = []

        with self._connect() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, (state, state))
                rows = [dict(row) for row in cursor.fetchall()]

        for row in rows:
            searchable = " ".join(
                [
                    row.get("title", ""),
                    row.get("citation", ""),
                    row.get("snippet", ""),
                    " ".join(row.get("topics", [])),
                ]
            )
            tokens = self._tokenize(searchable)
            overlap = query_tokens.intersection(tokens)
            score = len(overlap) / max(len(query_tokens), 1) if query_tokens else 0.0
            if score > 0:
                scored.append((score, row))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [row for _, row in scored[:limit]]

    def upsert_precedent_records(self, records: list[dict]) -> int:
        if not records:
            return 0

        sql = """
        INSERT INTO precedent_corpus
        (state, title, citation, court, year, topics, snippet, source_url)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (state, citation)
        DO UPDATE SET
            title = EXCLUDED.title,
            court = EXCLUDED.court,
            year = EXCLUDED.year,
            topics = EXCLUDED.topics,
            snippet = EXCLUDED.snippet,
            source_url = EXCLUDED.source_url,
            updated_at = NOW();
        """

        inserted = 0
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for item in records:
                    state = (item.get("state") or "").strip().lower()
                    if state not in SUPPORTED_STATES:
                        continue

                    title = (item.get("title") or "").strip()
                    citation = (item.get("citation") or item.get("source_url") or "").strip()
                    snippet = (item.get("snippet") or "").strip()
                    source_url = item.get("source_url")

                    if not self._is_high_quality_precedent_row(
                        title=title,
                        snippet=snippet,
                        citation=citation,
                        source_url=source_url,
                    ):
                        continue

                    cursor.execute(
                        sql,
                        (
                            state,
                            title[:500],
                            citation[:300],
                            item.get("court", "Public Source")[:250],
                            item.get("year"),
                            item.get("topics", []),
                            snippet[:5000],
                            source_url,
                        ),
                    )
                    inserted += 1
                connection.commit()
        return inserted

    def create_scheduler_run(self) -> int:
        sql = """
        INSERT INTO scheduler_run_audit (status)
        VALUES ('running')
        RETURNING id;
        """

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                row = cursor.fetchone()
                connection.commit()
                return int(row[0])

    def finalize_scheduler_run(
        self,
        run_id: int,
        status: str,
        sources_processed: int,
        urls_attempted: int,
        inserted_count: int,
        failed_urls: list[str],
        error_message: str | None = None,
    ) -> None:
        sql = """
        UPDATE scheduler_run_audit
        SET
            ended_at = NOW(),
            status = %s,
            sources_processed = %s,
            urls_attempted = %s,
            inserted_count = %s,
            failed_count = %s,
            failed_urls = %s,
            error_message = %s
        WHERE id = %s;
        """

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql,
                    (
                        status,
                        sources_processed,
                        urls_attempted,
                        inserted_count,
                        len(failed_urls),
                        failed_urls,
                        error_message,
                        run_id,
                    ),
                )
                connection.commit()

    def list_scheduler_runs(self, limit: int = 30) -> list[dict]:
        sql = """
        SELECT
            id,
            started_at,
            ended_at,
            status,
            sources_processed,
            urls_attempted,
            inserted_count,
            failed_count,
            failed_urls,
            error_message
        FROM scheduler_run_audit
        ORDER BY started_at DESC
        LIMIT %s;
        """

        with self._connect() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, (limit,))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]

    def data_quality_summary(self, *, capture_snapshot: bool = False, source: str = "manual", run_id: int | None = None) -> dict:
        query = """
        SELECT state, title, citation, snippet, source_url
        FROM precedent_corpus;
        """

        with self._connect() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query)
                rows = [dict(row) for row in cursor.fetchall()]

        total_records = len(rows)
        trusted_records = 0
        high_quality_records = 0
        domain_counts: dict[str, int] = {}
        state_counts: dict[str, int] = {}

        for row in rows:
            source_url = row.get("source_url")
            state = (row.get("state") or "unknown").strip().lower()
            state_counts[state] = state_counts.get(state, 0) + 1

            if self._is_trusted_source(source_url):
                trusted_records += 1

            if self._is_high_quality_precedent_row(
                title=row.get("title", ""),
                snippet=row.get("snippet", ""),
                citation=row.get("citation", ""),
                source_url=source_url,
            ):
                high_quality_records += 1

            try:
                host = (urlparse(source_url).hostname or "unknown").lower() if source_url else "unknown"
            except Exception:
                host = "unknown"
            domain_counts[host] = domain_counts.get(host, 0) + 1

        rejected_or_low_quality = max(total_records - high_quality_records, 0)
        trusted_pct = round((trusted_records * 100.0 / total_records), 2) if total_records else 0.0
        high_quality_pct = round((high_quality_records * 100.0 / total_records), 2) if total_records else 0.0

        top_domains = sorted(
            [{"domain": domain, "count": count} for domain, count in domain_counts.items()],
            key=lambda item: item["count"],
            reverse=True,
        )[:10]

        state_distribution = sorted(
            [{"state": state, "count": count} for state, count in state_counts.items()],
            key=lambda item: item["count"],
            reverse=True,
        )

        recent_runs = self.list_scheduler_runs(limit=20)
        scheduler_failures = sum(int(item.get("failed_count") or 0) for item in recent_runs)
        scheduler_attempted_urls = sum(int(item.get("urls_attempted") or 0) for item in recent_runs)
        scheduler_inserted = sum(int(item.get("inserted_count") or 0) for item in recent_runs)

        summary = {
            "total_precedent_records": total_records,
            "trusted_source_records": trusted_records,
            "high_quality_records": high_quality_records,
            "rejected_or_low_quality_records": rejected_or_low_quality,
            "trusted_source_pct": trusted_pct,
            "high_quality_pct": high_quality_pct,
            "top_source_domains": top_domains,
            "state_distribution": state_distribution,
            "scheduler_20_runs": {
                "urls_attempted": scheduler_attempted_urls,
                "records_inserted": scheduler_inserted,
                "url_failures": scheduler_failures,
            },
        }

        if capture_snapshot:
            self.record_data_quality_snapshot(summary=summary, source=source, run_id=run_id)

        return summary

    def record_data_quality_snapshot(self, *, summary: dict, source: str, run_id: int | None = None) -> int:
        scheduler_rollup = summary.get("scheduler_20_runs") or {}

        sql = """
        INSERT INTO data_quality_history (
            source,
            run_id,
            total_precedent_records,
            trusted_source_records,
            high_quality_records,
            rejected_or_low_quality_records,
            trusted_source_pct,
            high_quality_pct,
            scheduler_urls_attempted,
            scheduler_records_inserted,
            scheduler_url_failures
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
        """

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql,
                    (
                        source[:80] if source else "manual",
                        run_id,
                        int(summary.get("total_precedent_records") or 0),
                        int(summary.get("trusted_source_records") or 0),
                        int(summary.get("high_quality_records") or 0),
                        int(summary.get("rejected_or_low_quality_records") or 0),
                        float(summary.get("trusted_source_pct") or 0),
                        float(summary.get("high_quality_pct") or 0),
                        int(scheduler_rollup.get("urls_attempted") or 0),
                        int(scheduler_rollup.get("records_inserted") or 0),
                        int(scheduler_rollup.get("url_failures") or 0),
                    ),
                )
                row = cursor.fetchone()
                connection.commit()
                return int(row[0])

    def list_data_quality_history(self, limit: int = 30) -> list[dict]:
        sql = """
        SELECT
            id,
            captured_at,
            source,
            run_id,
            total_precedent_records,
            trusted_source_records,
            high_quality_records,
            rejected_or_low_quality_records,
            trusted_source_pct,
            high_quality_pct,
            scheduler_urls_attempted,
            scheduler_records_inserted,
            scheduler_url_failures
        FROM data_quality_history
        ORDER BY captured_at DESC
        LIMIT %s;
        """

        with self._connect() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, (limit,))
                rows = [dict(row) for row in cursor.fetchall()]
                return rows
