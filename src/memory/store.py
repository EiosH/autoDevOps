import json

from core.models import MemoryRecord, MemoryType
from memory.backend import (
    MemoryBackend,
    keyword_overlap_ratio,
    keyword_overlap_score,
)
from memory.file_backend import FileBackend
from memory.postgres_backend import PostgresBackend


class MemoryStore:
    def __init__(self, backend: MemoryBackend | None = None) -> None:
        self._backend = backend
        self.records: list[MemoryRecord] = (
            backend.list_all() if backend is not None else []
        )

    def add(self, record: MemoryRecord) -> None:
        if self._backend is not None:
            self._backend.add(record)
            self._refresh_records()
            return
        self.records.append(record)

    def list_all(self) -> list[MemoryRecord]:
        self._refresh_records()
        return list(self.records)

    def list_by_type(self, memory_type: MemoryType) -> list[MemoryRecord]:
        if isinstance(self._backend, PostgresBackend):
            return self._backend.list_by_type(memory_type)
        return [
            record for record in self.list_all() if record.memory_type == memory_type
        ]

    def recall_long_term(
        self,
        project_id: str,
        keywords: list[str],
        limit: int = 5,
    ) -> list[MemoryRecord]:
        if isinstance(self._backend, PostgresBackend):
            return self._backend.recall_long_term(project_id, keywords, limit)
        return self._recall_long_term_in_memory(project_id, keywords, limit)

    def is_duplicate_long_term(
        self,
        project_id: str,
        problem: str,
        keywords: list[str],
    ) -> bool:
        if isinstance(self._backend, PostgresBackend):
            return self._backend.is_duplicate_long_term(
                project_id, problem, keywords
            )
        return self._is_duplicate_long_term_in_memory(project_id, problem, keywords)

    def find_by_task_id(self, task_id: str) -> list[MemoryRecord]:
        return [
            record
            for record in self.list_all()
            if record.metadata.get("task_id") == task_id
        ]

    def find_by_agent_name(self, agent_name: str) -> list[MemoryRecord]:
        return [
            record
            for record in self.list_all()
            if record.metadata.get("agent_name") == agent_name
        ]

    def search(self, keyword: str) -> list[MemoryRecord]:
        return [record for record in self.list_all() if keyword in record.content]

    def _refresh_records(self) -> None:
        if self._backend is not None:
            self.records = self._backend.list_all()

    def _recall_long_term_in_memory(
        self,
        project_id: str,
        keywords: list[str],
        limit: int,
    ) -> list[MemoryRecord]:
        if not keywords:
            return []

        scored: list[tuple[int, MemoryRecord]] = []
        for record in self.list_by_type(MemoryType.LONG_TERM):
            if record.metadata.get("project") not in (None, project_id):
                continue
            record_keywords = list(record.metadata.get("keywords", []))
            try:
                payload = json.loads(record.content)
                record_keywords.extend(payload.get("keywords", []))
            except json.JSONDecodeError:
                pass
            score = keyword_overlap_score(keywords, record_keywords)
            if score > 0:
                scored.append((score, record))

        scored.sort(key=lambda item: (-item[0], -item[1].created_at))
        return [record for _, record in scored[:limit]]

    def _is_duplicate_long_term_in_memory(
        self,
        project_id: str,
        problem: str,
        keywords: list[str],
    ) -> bool:
        new_problem = (problem or "").strip().lower()
        for record in self.list_by_type(MemoryType.LONG_TERM):
            if record.metadata.get("project") != project_id:
                continue
            try:
                old = json.loads(record.content)
            except json.JSONDecodeError:
                continue
            old_problem = (old.get("problem") or "").strip().lower()
            if new_problem and new_problem == old_problem:
                return True
            old_keywords = list(old.get("keywords", []))
            old_keywords.extend(record.metadata.get("keywords", []))
            if keyword_overlap_ratio(keywords, old_keywords) >= 0.6:
                return True
        return False


__all__ = ["FileBackend", "MemoryStore", "PostgresBackend"]
