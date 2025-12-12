-- Vector similarity search with optional metadata filters for paper_embeddings.
-- Intended to be called by the `search_papers` Edge Function.

CREATE OR REPLACE FUNCTION search_papers_by_embedding(
    input_embedding VECTOR(1536),
    filter_conference TEXT[] DEFAULT NULL,
    filter_year INTEGER[] DEFAULT NULL,
    filter_status TEXT[] DEFAULT NULL,
    filter_keywords TEXT[] DEFAULT NULL,
    offset_rows INTEGER DEFAULT 0,
    limit_rows INTEGER DEFAULT 20
)
RETURNS TABLE (
    id BIGINT,
    paper_uid TEXT,
    conference TEXT,
    year INTEGER,
    status TEXT,
    title TEXT,
    keywords TEXT[],
    summary TEXT,
    raw_excerpt TEXT,
    data JSONB,
    created_at TIMESTAMPTZ,
    distance DOUBLE PRECISION,
    total_count BIGINT
)
LANGUAGE SQL STABLE
AS $$
    SELECT
        pe.id,
        pe.paper_uid,
        pe.conference,
        pe.year,
        pe.status,
        pe.title,
        pe.keywords,
        pe.summary,
        pe.raw_excerpt,
        pe.data,
        pe.created_at,
        pe.embedding <=> input_embedding AS distance,
        COUNT(*) OVER() AS total_count
    FROM paper_embeddings pe
    WHERE
        (filter_conference IS NULL OR array_length(filter_conference, 1) = 0 OR pe.conference = ANY(filter_conference))
        AND (filter_year IS NULL OR array_length(filter_year, 1) = 0 OR pe.year = ANY(filter_year))
        AND (filter_status IS NULL OR array_length(filter_status, 1) = 0 OR pe.status = ANY(filter_status))
        AND (filter_keywords IS NULL OR array_length(filter_keywords, 1) = 0 OR pe.keywords && filter_keywords)
    ORDER BY pe.embedding <=> input_embedding
    OFFSET GREATEST(offset_rows, 0)
    LIMIT CASE WHEN limit_rows IS NULL OR limit_rows <= 0 THEN 20 ELSE limit_rows END;
$$;

