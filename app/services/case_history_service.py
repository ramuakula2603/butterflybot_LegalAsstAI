import os
from contextlib import contextmanager
from typing import Iterator

import psycopg2
from psycopg2.extras import RealDictCursor


class CaseHistoryService:
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

    def init_schema(self) -> None:
        statement = """
        CREATE TABLE IF NOT EXISTS case_history (
            id SERIAL PRIMARY KEY,
            case_title TEXT NOT NULL,
            client_name TEXT NOT NULL,
            case_type TEXT NOT NULL,
            court_level TEXT NOT NULL,
            state TEXT NOT NULL,
            case_district TEXT NOT NULL DEFAULT '',
            facts_summary TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
        migration = """
        ALTER TABLE case_history
        ADD COLUMN IF NOT EXISTS case_district TEXT NOT NULL DEFAULT '';
        """

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement)
                cursor.execute(migration)
                connection.commit()

    def create_case(self, payload: dict) -> dict:
        insert_sql = """
        INSERT INTO case_history (
            case_title, client_name, case_type, court_level, state, case_district, facts_summary
        )
        VALUES (%(case_title)s, %(client_name)s, %(case_type)s, %(court_level)s, %(state)s, %(case_district)s, %(facts_summary)s)
        RETURNING id, case_title, client_name, case_type, court_level, state, case_district, facts_summary, created_at;
        """

        with self._connect() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(insert_sql, payload)
                row = cursor.fetchone()
                connection.commit()
                return dict(row) if row else {}

    def list_cases(self, limit: int = 20) -> list[dict]:
        query = """
        SELECT id, case_title, client_name, case_type, court_level, state, case_district, facts_summary, created_at
        FROM case_history
        ORDER BY created_at DESC
        LIMIT %s;
        """

        with self._connect() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, (limit,))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]

    def get_case(self, case_id: int) -> dict | None:
        query = """
        SELECT id, case_title, client_name, case_type, court_level, state, case_district, facts_summary, created_at
        FROM case_history
        WHERE id = %s;
        """

        with self._connect() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, (case_id,))
                row = cursor.fetchone()
                return dict(row) if row else None

    def update_case(self, case_id: int, payload: dict) -> dict | None:
        update_sql = """
        UPDATE case_history
        SET
            case_title = %(case_title)s,
            client_name = %(client_name)s,
            case_type = %(case_type)s,
            court_level = %(court_level)s,
            state = %(state)s,
            case_district = %(case_district)s,
            facts_summary = %(facts_summary)s
        WHERE id = %(case_id)s
        RETURNING id, case_title, client_name, case_type, court_level, state, case_district, facts_summary, created_at;
        """

        with self._connect() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(update_sql, {**payload, "case_id": case_id})
                row = cursor.fetchone()
                connection.commit()
                return dict(row) if row else None

    def delete_case(self, case_id: int) -> bool:
        delete_sql = """
        DELETE FROM case_history
        WHERE id = %s;
        """

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(delete_sql, (case_id,))
                affected = cursor.rowcount
                connection.commit()
                return affected > 0
