import os

from memory.backend import MemoryBackend
from memory.file_backend import FileBackend
from memory.postgres_backend import PostgresBackend
from memory.store import MemoryStore
from utils.path_helper import get_project_root


def create_memory_store() -> MemoryStore:
    backend_preference = os.environ.get("MEMORY_BACKEND", "auto").lower()
    database_url = os.environ.get("MEMORY_DATABASE_URL") or os.environ.get(
        "DATABASE_URL"
    )

    use_postgres = backend_preference == "postgres" or (
        backend_preference == "auto" and database_url
    )

    if use_postgres:
        if not database_url:
            raise ValueError(
                "MEMORY_BACKEND=postgres requires MEMORY_DATABASE_URL or DATABASE_URL"
            )
        return MemoryStore(PostgresBackend(database_url))

    memory_path = get_project_root() / ".memory" / "long_term.json"
    return MemoryStore(FileBackend(memory_path))
