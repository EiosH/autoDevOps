from core.models import MemoryRecord, MemoryType


class MemoryStore:
    records: list[MemoryRecord]

    def __init__(self):
        self.records = []

    def add(self, record: MemoryRecord):
        self.records.append(record)

    def list_all(self):
        return self.records

    def list_by_type(self, memory_type: MemoryType):
        return [record for record in self.records if record.memory_type == memory_type]

    def find_by_task_id(self, task_id: str):
        return [
            record for record in self.records
            if record.metadata.get("task_id") == task_id
        ]

    def find_by_agent_name(self, agent_name: str):
        return [
            record for record in self.records
            if record.metadata.get("agent_name") == agent_name
        ]

    def search(self, keyword: str):
        return [record for record in self.records if keyword in record.content]
