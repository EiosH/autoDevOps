import json
from pathlib import Path

from core.models import MemoryRecord


class FileBackend:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.records: list[MemoryRecord] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.records = [MemoryRecord.model_validate(item) for item in raw]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [record.model_dump(mode="json") for record in self.records]
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, record: MemoryRecord) -> None:
        existing_ids = {item.memory_id for item in self.records}
        if record.memory_id in existing_ids:
            self.records = [item for item in self.records if item.memory_id != record.memory_id]
        self.records.append(record)
        self.save()

    def list_all(self) -> list[MemoryRecord]:
        return list(self.records)
