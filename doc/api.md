# Supabase Edge Functions API

- Base URL: `https://ficmpqqydzbptnoyroaz.supabase.co/functions/v1/`
- Content type: always send `Content-Type: application/json`.
- Authentication: if your project requires it, include `Authorization: Bearer <SUPABASE_SERVICE_ROLE_KEY>` (or another service key for trusted backends).

## POST `match_papers`
- URL: `${BASE_URL}match_papers`
- Purpose: search papers either by a provided embedding or by an existing `paper_uid`'s stored embedding.
- Body:
  - `embedding` (number[1536], optional): search vector. If provided, it is used preferentially.
  - `paper_uid` (string, optional): use this paper's stored embedding to find similar items.
  - `threshold` (number, optional): similarity cutoff; default `0.4`.
  - `match_count` (integer, optional): max rows to return; default `20`.
- Rules: at least one of `embedding` or `paper_uid` is required; `embedding` must be an array of length `1536`; `paper_uid` must be a non-empty string. The function fetches one extra row and removes any self-match with `distance === 0`, then returns up to `match_count` results.
- Response: array of rows from the vector RPCs, each containing `distance` (cosine distance; smaller is more similar).
- Example (by embedding):
```bash
curl -X POST "${BASE_URL}match_papers" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "embedding": [0.12, -0.08, 0.33, "... up to 1536 values ..."],
    "threshold": 0.35,
    "match_count": 10
  }'
```
- Example (by paper id):
```bash
curl -X POST "${BASE_URL}match_papers" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "paper_uid": "paper-001",
    "match_count": 15
  }'
```

## POST `search_papers`
- URL: `${BASE_URL}search_papers`
- Purpose: search `paper_embeddings` by embedding similarity (preferred) with optional filters, or fall back to text search.
- Body:
  - `embedding` (number[1536], optional): embedding to search by. When provided, embedding search is used.
  - `query` (string, optional): free-text matched against `title`, `summary`, `raw_excerpt` (used when `embedding` is not provided).
  - `page` (integer, optional): 1-based page index; default `1`.
  - `page_size` (integer, optional): items per page; default `20`.
  - `conference` (string[], optional): filter by conference names.
  - `year` (int[], optional): filter by years.
  - `status` (string[], optional): filter by status labels.
  - `keywords` (string[], optional): matches if any keyword overlaps.
- Response: `{ data: PaperRow[], count: number, page: number, page_size: number }` where `PaperRow` is a `paper_embeddings` row without the `embedding` field. Embedding search also returns a `distance` field per row (smaller = more similar).
- RPC: `search_papers_by_embedding(...)` defined in `migrations/002_search_papers_by_embedding.sql` (supports filters, offset, and limit).
- Example:
```bash
curl -X POST "${BASE_URL}search_papers" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "embedding": [0.12, -0.08, 0.33, "... up to 1536 values ..."],
    "query": "diffusion",
    "conference": ["ICLR"],
    "year": [2024],
    "keywords": ["vision"]
  }'
```

## POST `recommend_papers`
- URL: `${BASE_URL}recommend_papers`
- Body:
  - `user_id` (string): required user identifier passed to the RPC as `uid`.
  - `page` (integer, optional): 1-based page index; default `1`.
  - `page_size` (integer, optional): items per page; default `20`.
  - `alpha` (number, optional): weight parameter; default `0.85`.
  - `beta` (number, optional): weight parameter; default `0.15`.
  - `conference` (string[], optional): filter by conference names.
  - `year` (int[], optional): filter by publication years.
  - `status` (string[], optional): filter by status labels.
  - `keywords` (string[], optional): filter by keywords.
- Response: array of recommendation rows from `recommend_papers_hybrid` (fields defined by that RPC). If no filters are provided, it falls back to `recommend_papers_hybrid_no_filter`.
- Example:
```bash
curl -X POST "${BASE_URL}recommend_papers" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "abc123",
    "page": 2,
    "page_size": 10,
    "alpha": 0.85,
    "beta": 0.15,
    "conference": ["ICLR", "NeurIPS"],
    "year": [2023, 2024],
    "status": ["accepted"],
    "keywords": ["diffusion", "vision"]
  }'
```

## POST `update_interest`
- URL: `${BASE_URL}update_interest`
- Body:
  - `user_id` (string): required user identifier passed to the `update_interest_embedding` RPC as `uid`.
  - `paper_uid` (string): required paper identifier to blend into the user's interest embedding.
- Response: `{ "success": true }` on success; on error returns a 500 with the RPC error message.
- Example:
```bash
curl -X POST "${BASE_URL}update_interest" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "abc123",
    "paper_uid": "paper-001"
  }'
```

## GET `filter_options`
- URL: `${BASE_URL}filter_options`
- Purpose: return distinct filter options derived from `paper_embeddings`, cached for 1 week in `kv_store_ttl`.
- Request: no body.
- Response: `{ source: "cache" | "fresh", data: { conference: string[], year: number[], status: string[], keywords: string[] } }`.
- Notes: fetches `conference`, `year`, `status`, `keywords` distinct values; caches under `key = "filter_options"` with a 7-day TTL.
- Example:
```bash
curl -X GET "${BASE_URL}filter_options" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
```
