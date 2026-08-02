from __future__ import annotations

from core.models import MemoryRecord, MemoryType
from memory.backend import (
    load_schema_sql,
    record_to_structured_fields,
    row_to_record,
)

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
except ImportError:  # pragma: no cover - optional dependency
    psycopg = None
    dict_row = None
    Jsonb = None

_KEYWORD_MATCH_SQL = """
    lower(stored_kw) = lower(query_kw)
    OR strpos(lower(stored_kw), lower(query_kw)) > 0
    OR strpos(lower(query_kw), lower(stored_kw)) > 0
"""


class PostgresBackend:
    def __init__(self, database_url: str) -> None:
        if psycopg is None or Jsonb is None:
            raise ImportError(
                "psycopg is required for PostgresBackend. Install with: pip install 'psycopg[binary]'"
            )
        self.database_url = database_url
        self._ensure_schema()

    def _connect(self, *, autocommit: bool = False):
        return psycopg.connect(
            self.database_url,
            row_factory=dict_row,
            autocommit=autocommit,
        )

    def _ensure_schema(self) -> None:
        with self._connect(autocommit=True) as conn:
            for statement in load_schema_sql().split(";"):
                sql = statement.strip()
                if sql:
                    conn.execute(sql)

    def add(self, record: MemoryRecord) -> None:
        fields = record_to_structured_fields(record)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_records (
                    memory_id, memory_type, source, created_at,
                    project_id, kind, run_id, keywords,
                    problem, resolution, content
                ) VALUES (
                    %(memory_id)s, %(memory_type)s, %(source)s,
                    to_timestamp(%(created_at)s),
                    %(project_id)s, %(kind)s, %(run_id)s, %(keywords)s,
                    %(problem)s, %(resolution)s, %(content)s
                )
                ON CONFLICT (memory_id) DO UPDATE SET
                    memory_type = EXCLUDED.memory_type,
                    source = EXCLUDED.source,
                    created_at = EXCLUDED.created_at,
                    project_id = EXCLUDED.project_id,
                    kind = EXCLUDED.kind,
                    run_id = EXCLUDED.run_id,
                    keywords = EXCLUDED.keywords,
                    problem = EXCLUDED.problem,
                    resolution = EXCLUDED.resolution,
                    content = EXCLUDED.content
                """,
                {
                    "memory_id": record.memory_id,
                    "memory_type": record.memory_type.value,
                    "source": record.source,
                    "created_at": record.created_at,
                    "project_id": fields["project_id"],
                    "kind": fields["kind"],
                    "run_id": fields["run_id"],
                    "keywords": [
                        kw.lower() for kw in fields["keywords"] if isinstance(kw, str)
                    ],
                    "problem": fields["problem"],
                    "resolution": fields["resolution"],
                    "content": Jsonb(fields["content"]),
                },
            )
            conn.commit()

    def list_all(self) -> list[MemoryRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT memory_id, memory_type, source, created_at,
                       project_id, kind, run_id, keywords,
                       problem, resolution, content
                FROM memory_records
                ORDER BY created_at ASC
                """
            ).fetchall()
        return [row_to_record(row) for row in rows]

    def list_by_type(self, memory_type: MemoryType) -> list[MemoryRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT memory_id, memory_type, source, created_at,
                       project_id, kind, run_id, keywords,
                       problem, resolution, content
                FROM memory_records
                WHERE memory_type = %(memory_type)s
                ORDER BY created_at ASC
                """,
                {"memory_type": memory_type.value},
            ).fetchall()
        return [row_to_record(row) for row in rows]

    def recall_long_term(
        self,
        project_id: str,
        keywords: list[str],
        limit: int = 5,
    ) -> list[MemoryRecord]:
        normalized = [
            kw.lower() for kw in keywords if isinstance(kw, str) and kw.strip()
        ]
        if not normalized:
            return []

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT memory_id, memory_type, source, created_at,
                       project_id, kind, run_id, keywords,
                       problem, resolution, content,
                       (
                           SELECT COUNT(*)::int
                           FROM unnest(%(query_keywords)s::text[]) AS q(query_kw)
                           WHERE EXISTS (
                               SELECT 1
                               FROM unnest(keywords) AS k(stored_kw)
                               WHERE {_KEYWORD_MATCH_SQL}
                           )
                       ) AS overlap_score
                FROM memory_records
                WHERE memory_type = %(memory_type)s
                  AND project_id = %(project_id)s
                  AND EXISTS (
                      SELECT 1
                      FROM unnest(keywords) AS k(stored_kw),
                           unnest(%(query_keywords)s::text[]) AS q(query_kw)
                      WHERE {_KEYWORD_MATCH_SQL}
                  )
                ORDER BY overlap_score DESC, created_at DESC
                LIMIT %(limit)s
                """,
                {
                    "memory_type": MemoryType.LONG_TERM.value,
                    "project_id": project_id,
                    "query_keywords": normalized,
                    "limit": int(limit),
                },
            ).fetchall()
        return [row_to_record(row) for row in rows]

    def is_duplicate_long_term(
        self,
        project_id: str,
        problem: str,
        keywords: list[str],
    ) -> bool:
        normalized_keywords = [
            kw.lower() for kw in keywords if isinstance(kw, str) and kw.strip()
        ]
        normalized_problem = (problem or "").strip().lower()

        with self._connect() as conn:
            if normalized_problem:
                row = conn.execute(
                    """
                    SELECT 1
                    FROM memory_records
                    WHERE memory_type = %(memory_type)s
                      AND project_id = %(project_id)s
                      AND problem IS NOT NULL
                      AND lower(problem) = %(problem)s
                    LIMIT 1
                    """,
                    {
                        "memory_type": MemoryType.LONG_TERM.value,
                        "project_id": project_id,
                        "problem": normalized_problem,
                    },
                ).fetchone()
                if row is not None:
                    return True

            if not normalized_keywords:
                return False

            row = conn.execute(
                f"""
                SELECT 1
                FROM memory_records
                WHERE memory_type = %(memory_type)s
                  AND project_id = %(project_id)s
                  AND (
                      SELECT COUNT(*)::float
                      FROM unnest(%(keywords)s::text[]) AS q(query_kw)
                      WHERE EXISTS (
                          SELECT 1
                          FROM unnest(keywords) AS k(stored_kw)
                          WHERE {_KEYWORD_MATCH_SQL}
                      )
                  ) / cardinality(%(keywords)s::text[])::float >= 0.6
                LIMIT 1
                """,
                {
                    "memory_type": MemoryType.LONG_TERM.value,
                    "project_id": project_id,
                    "keywords": normalized_keywords,
                },
            ).fetchone()
        return row is not None
