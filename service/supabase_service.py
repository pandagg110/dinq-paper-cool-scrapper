import os

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

_supabase: Client | None = None


def get_supabase_client() -> Client:
    """Create (and cache) the Supabase client using environment variables."""
    global _supabase

    if _supabase is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment.")
        _supabase = create_client(url, key)

    return _supabase


def match_papers(query_embedding: list[float], match_count: int = 10, threshold: float = 0.35):
    supabase = get_supabase_client()
    response = supabase.rpc(
        "match_papers",
        {
            "query_embedding": query_embedding,
            "match_count": match_count,
            "threshold": threshold,
        },
    ).execute()

    if getattr(response, "error", None):
        raise RuntimeError(response.error)

    return getattr(response, "data", response)
