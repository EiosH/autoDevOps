CREATE TABLE IF NOT EXISTS memory_records (
    memory_id    TEXT PRIMARY KEY,
    memory_type  TEXT NOT NULL,
    source       TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

    project_id   TEXT NOT NULL,
    kind         TEXT NOT NULL,
    run_id       TEXT,
    keywords     TEXT[] NOT NULL DEFAULT '{}',

    problem      TEXT,
    resolution   TEXT,

    content      JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_project_kind
    ON memory_records (project_id, kind);

CREATE INDEX IF NOT EXISTS idx_memory_type
    ON memory_records (memory_type);

CREATE INDEX IF NOT EXISTS idx_memory_keywords
    ON memory_records USING GIN (keywords);

CREATE INDEX IF NOT EXISTS idx_memory_content
    ON memory_records USING GIN (content jsonb_path_ops);
