-- Enable pgvector (requires the extension to be installed on the server)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS paper_embeddings (
    id             BIGSERIAL PRIMARY KEY,
    paper_uid      TEXT NOT NULL,                -- stable id from source (e.g., paper_id in JSON)
    conference     TEXT NOT NULL,
    year           INTEGER NOT NULL,
    status         TEXT,                         -- highlight / oral / spotlight / award / etc.
    title          TEXT NOT NULL,
    keywords       TEXT[] DEFAULT '{}',
    summary        TEXT,
    raw_excerpt    TEXT,
    data           JSONB,                        -- full paper object from the scraper
    embedding      VECTOR(1536) NOT NULL,        -- text-embedding-3-small dimension (fits IVFFLAT limit)
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Uniqueness on source identity.
CREATE UNIQUE INDEX IF NOT EXISTS paper_embeddings_uid_idx
    ON paper_embeddings (paper_uid);

-- Filter/sort helpers.
CREATE INDEX IF NOT EXISTS paper_embeddings_conf_year_status_idx
    ON paper_embeddings (conference, year, status);

CREATE INDEX IF NOT EXISTS paper_embeddings_keywords_idx
    ON paper_embeddings USING GIN (keywords);

-- Vector similarity index (cosine). Run after loading data; adjust lists as needed.
CREATE INDEX IF NOT EXISTS paper_embeddings_embedding_idx
    ON paper_embeddings USING IVFFLAT (embedding vector_cosine_ops) WITH (lists = 100);

-- (Optional) smaller table for metadata-only search paths
-- CREATE TABLE paper_metadata AS SELECT id, paper_uid, conference, year, status, title, keywords, summary FROM paper_embeddings;
