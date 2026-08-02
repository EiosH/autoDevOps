from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from core.models import MemoryRecord, MemoryType


class MemoryBackend(Protocol):
    def add(self, record: MemoryRecord) -> None: ...

    def list_all(self) -> list[MemoryRecord]: ...


def record_to_structured_fields(record: MemoryRecord) -> dict[str, Any]:
    try:
        body = json.loads(record.content)
    except json.JSONDecodeError:
        body = {"summary": record.content}

    if not isinstance(body, dict):
        body = {"summary": str(body)}

    keywords = record.metadata.get("keywords") or body.get("keywords") or []
    if not isinstance(keywords, list):
        keywords = []

    return {
        "project_id": record.metadata.get("project", "default"),
        "kind": record.metadata.get("kind") or body.get("kind", "memory"),
        "run_id": record.metadata.get("run_id"),
        "keywords": [kw for kw in keywords if isinstance(kw, str)],
        "problem": body.get("problem"),
        "resolution": body.get("resolution"),
        "content": body,
    }


def row_to_record(row: dict[str, Any]) -> MemoryRecord:
    content = row["content"]
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False)

    created_at = row["created_at"]
    if isinstance(created_at, datetime):
        created_at_value = created_at.timestamp()
    else:
        created_at_value = float(created_at)

    keywords = row.get("keywords") or []
    return MemoryRecord(
        memory_id=row["memory_id"],
        memory_type=MemoryType(row["memory_type"]),
        content=content,
        source=row["source"],
        metadata={
            "kind": row.get("kind"),
            "keywords": list(keywords),
            "project": row.get("project_id"),
            "run_id": row.get("run_id"),
        },
        created_at=created_at_value,
    )


def load_schema_sql() -> str:
    return (Path(__file__).resolve().parent / "schema.sql").read_text(encoding="utf-8")


def normalize_keywords(keywords: list[str]) -> list[str]:
    return [kw.lower() for kw in keywords if isinstance(kw, str) and kw.strip()]


def keywords_match(query_kw: str, stored_kw: str) -> bool:
    query = query_kw.lower()
    stored = stored_kw.lower()
    if not query or not stored:
        return False
    return query == stored or query in stored or stored in query


def keyword_overlap_score(
    query_keywords: list[str], stored_keywords: list[str]
) -> int:
    score = 0
    for query_kw in normalize_keywords(query_keywords):
        if any(
            keywords_match(query_kw, stored_kw)
            for stored_kw in normalize_keywords(stored_keywords)
        ):
            score += 1
    return score


def keyword_overlap_ratio(
    query_keywords: list[str], stored_keywords: list[str]
) -> float:
    normalized = normalize_keywords(query_keywords)
    if not normalized:
        return 0.0
    return keyword_overlap_score(query_keywords, stored_keywords) / len(normalized)
