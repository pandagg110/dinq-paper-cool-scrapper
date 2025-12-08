"""Ingest scraped paper JSON files into Supabase (paper_embeddings table) with progress and resume."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from supabase import Client, create_client

from service.embedding_service import generate_embedding_by_paper_obj


CHECKPOINT_PATH = Path("data_ready/.ingest_checkpoint.json")


load_dotenv()  # load .env if present


def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment.")
    return create_client(url, key)


def chunked(seq: List[Any], size: int):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def build_rows(
    data: Dict[str, Any], start: int, end: int
) -> List[Dict[str, Any]]:
    conference = data.get("conference")
    year = data.get("year")
    status = data.get("status")
    rows: List[Dict[str, Any]] = []

    papers = data.get("papers", [])
    for paper in papers[start:end]:
        paper_uid = paper.get("paper_id")
        title = paper.get("title")
        if not paper_uid or not title:
            continue

        embedding = generate_embedding_by_paper_obj(paper)

        rows.append(
            {
                "paper_uid": paper_uid,
                "conference": conference,
                "year": year,
                "status": status,
                "title": title,
                "keywords": paper.get("keywords") or [],
                "summary": paper.get("summary"),
                "raw_excerpt": paper.get("raw_excerpt"),
                "data": paper,
                "embedding": embedding,
            }
        )
    return rows


def load_checkpoint() -> Dict[str, Any]:
    if not CHECKPOINT_PATH.exists():
        return {"offsets": {}, "done": []}
    try:
        return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"offsets": {}, "done": []}


def save_checkpoint(state: Dict[str, Any]) -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CHECKPOINT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CHECKPOINT_PATH)


def file_counts(files: List[Path]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            counts[str(path)] = len(data.get("papers", []))
        except Exception:
            counts[str(path)] = 0
    return counts


def ingest_file(
    path: Path,
    client: Client,
    checkpoint: Dict[str, Any],
    totals: Dict[str, int],
    processed_global: int,
    total_remaining: int,
    batch_size: int = 50,
) -> Tuple[int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    papers = data.get("papers", [])
    total = len(papers)
    offset = int(checkpoint["offsets"].get(str(path), 0))

    if offset >= total:
        checkpoint["done"] = list(sorted(set(checkpoint.get("done", [])) | {str(path)}))
        checkpoint["offsets"].pop(str(path), None)
        save_checkpoint(checkpoint)
        print(f"[skip] {path.name}: already completed")
        return processed_global, total_remaining

    print(f"[start] {path.name}: {total} papers, resume at {offset}")
    offset_start = offset
    processed_file = 0

    for start in range(offset, total, batch_size):
        end = min(start + batch_size, total)
        batch_rows = build_rows(data, start, end)
        if not batch_rows:
            continue

        client.table("paper_embeddings").upsert(batch_rows, on_conflict="paper_uid").execute()

        offset = end
        processed_global += len(batch_rows)
        total_remaining -= len(batch_rows)
        processed_file += len(batch_rows)

        checkpoint["offsets"][str(path)] = offset
        save_checkpoint(checkpoint)

        print(
            f"[batch] {path.name} {offset}/{total} | global {processed_global}/{processed_global + total_remaining}"
        )

    checkpoint["done"] = list(sorted(set(checkpoint.get("done", [])) | {str(path)}))
    checkpoint["offsets"].pop(str(path), None)
    pending_start = max(total - offset_start, 0)
    remainder = max(pending_start - processed_file, 0)
    total_remaining -= remainder
    save_checkpoint(checkpoint)
    print(f"[ok] {path.name}: upserted {total} rows")
    return processed_global, total_remaining


def main() -> None:
    client = get_supabase_client()
    input_dir = Path("data_ready")
    files = sorted(input_dir.glob("*.json"))
    if not files:
        raise SystemExit("No JSON files found in data_ready/")

    checkpoint = load_checkpoint()
    counts = file_counts(files)

    processed_global = 0
    total_remaining = 0
    for path in files:
        total = counts.get(str(path), 0)
        offset = int(checkpoint.get("offsets", {}).get(str(path), 0))
        pending = max(total - offset, 0)
        total_remaining += pending

    if total_remaining == 0:
        print("Nothing to ingest; all files appear complete.")
        return

    print(f"Total remaining rows: {total_remaining}")

    for path in files:
        if str(path) in set(checkpoint.get("done", [])):
            print(f"[skip] {path.name}: marked done")
            continue
        try:
            processed_global, total_remaining = ingest_file(
                path, client, checkpoint, counts, processed_global, total_remaining
            )
        except Exception as exc:  # pragma: no cover - runtime guard
            print(f"[fail] {path.name}: {exc}")
            break


if __name__ == "__main__":
    main()
