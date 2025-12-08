"""Batch extract paper data from Cool Papers HTML dumps."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin

try:
    from bs4 import BeautifulSoup
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "Missing dependency beautifulsoup4. Install it with `pip install -r requirements.txt`."
    ) from exc


def split_authors(text: str) -> List[str]:
    cleaned = re.sub(r"\s+", " ", text).strip(" ,;")
    if not cleaned:
        return []
    parts = re.split(r"\s*(?:,|;| and | & )\s*", cleaned)
    return [part for part in (p.strip() for p in parts) if part]


def dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def to_int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    match = re.search(r"\d+", value)
    return int(match.group()) if match else None


def clean_raw_excerpt(text: str) -> str:
    """Remove leading indices like '#1 ' and trim whitespace."""
    cleaned = re.sub(r"^\s*#\s*\d+\s*", "", text or "")
    return cleaned.strip()


def extract_links(tag, base_url: Optional[str]) -> Dict[str, List[str]]:
    links: Dict[str, List[str]] = {}
    if tag is None:
        return links

    for anchor in tag.find_all("a"):
        url: Optional[str] = None
        for attr in ("href", "data", "data-href", "data-url"):
            candidate = anchor.get(attr)
            if candidate and candidate.strip():
                url = candidate.strip()
                break
        if not url:
            continue

        if base_url:
            url = urljoin(base_url, url)

        classes = " ".join(anchor.get("class", [])).lower()
        if "author" in classes:
            continue  # skip author search links

        label = (anchor.get_text(" ", strip=True) or "").lower()
        href_lower = url.lower()

        if "title-pdf" in classes or "pdf" in href_lower or label.startswith("[pdf"):
            key = "pdf"
        elif "supp" in classes or "supp" in href_lower or "supp" in label:
            key = "supp"
        elif "arxiv" in href_lower:
            key = "arxiv"
        elif "video" in href_lower or "youtube" in href_lower:
            key = "video"
        elif "slides" in href_lower or "slides" in label:
            key = "slides"
        elif "title-link" in classes or "venue" in href_lower:
            key = "venue"
        elif "paper.html" in href_lower:
            key = "detail"
        else:
            key = "link"

        links.setdefault(key, [])
        if url not in links[key]:
            links[key].append(url)

    return links


def merge_entries(current: dict, new: dict) -> dict:
    merged = dict(current)
    merged["authors"] = dedupe_preserve_order(
        [*(current.get("authors") or []), *(new.get("authors") or [])]
    )
    merged["subjects"] = dedupe_preserve_order(
        [*(current.get("subjects") or []), *(new.get("subjects") or [])]
    )
    merged["keywords"] = dedupe_preserve_order(
        [*(current.get("keywords") or []), *(new.get("keywords") or [])]
    )

    merged_links = dict(current.get("links") or {})
    for kind, urls in (new.get("links") or {}).items():
        dest = merged_links.setdefault(kind, [])
        for url in urls:
            if url not in dest:
                dest.append(url)
    merged["links"] = merged_links

    merged_scores = dict(current.get("scores") or {})
    for score_key, score_val in (new.get("scores") or {}).items():
        if merged_scores.get(score_key) is None and score_val is not None:
            merged_scores[score_key] = score_val
    merged["scores"] = merged_scores or None

    merged["paper_id"] = merged.get("paper_id") or new.get("paper_id")
    merged["index"] = merged.get("index") or new.get("index")
    merged["session"] = merged.get("session") or new.get("session")
    merged["time"] = merged.get("time") or new.get("time")
    merged["summary"] = merged.get("summary") or new.get("summary")
    merged["raw_excerpt"] = merged.get("raw_excerpt") or new.get("raw_excerpt")
    return merged


def parse_coolpapers_panels(soup, base_url: Optional[str]) -> List[dict]:
    """Parse Cool Papers layout (div.panel.paper cards)."""
    entries = []
    for panel in soup.select("div.panel.paper"):
        title_anchor = panel.select_one("a.title-link") or panel.find(
            ["h1", "h2", "h3", "h4", "h5"]
        )
        if not title_anchor:
            continue

        title = title_anchor.get_text(" ", strip=True)
        if not title:
            continue

        authors = [
            a.get_text(" ", strip=True) for a in panel.select("p.authors a.author")
        ]
        summary_tag = panel.select_one("p.summary") or panel.select_one(".abstract")
        summary = summary_tag.get_text(" ", strip=True) if summary_tag else None
        subjects = [
            a.get_text(" ", strip=True) for a in panel.select("p.subjects a")
        ]
        keywords_attr = panel.get("keywords") or ""
        keywords = dedupe_preserve_order(
            [kw.strip() for kw in keywords_attr.split(",") if kw.strip()]
        )

        links = extract_links(panel, base_url)

        pdf_tag = panel.select_one("a.title-pdf")
        pdf_url = None
        pdf_score = None
        if pdf_tag:
            pdf_url = pdf_tag.get("data") or pdf_tag.get("href")
            pdf_score = to_int(pdf_tag.get_text(" ", strip=True))
            if pdf_tag.find("sup"):
                pdf_score = to_int(pdf_tag.find("sup").get_text(" ", strip=True))
        if pdf_url:
            pdf_url = urljoin(base_url, pdf_url) if base_url else pdf_url
            links.setdefault("pdf", [])
            if pdf_url not in links["pdf"]:
                links["pdf"].append(pdf_url)

        detail_anchor = panel.select_one("h2.title > a[href]")
        detail_url = detail_anchor.get("href") if detail_anchor else None
        if detail_url:
            detail_url = urljoin(base_url, detail_url) if base_url else detail_url
            links.setdefault("detail", [])
            if detail_url not in links["detail"]:
                links["detail"].append(detail_url)

        venue_url = title_anchor.get("href") if title_anchor.has_attr("href") else None
        if venue_url:
            venue_url = urljoin(base_url, venue_url) if base_url else venue_url
            links.setdefault("venue", [])
            if venue_url not in links["venue"]:
                links["venue"].append(venue_url)

        kimi_tag = panel.select_one("a.title-kimi")
        kimi_score = None
        if kimi_tag and kimi_tag.find("sup"):
            kimi_score = to_int(kimi_tag.find("sup").get_text(" ", strip=True))

        index_tag = panel.select_one("h2.title span.index")
        index = to_int(index_tag.get_text(" ", strip=True)) if index_tag else None

        entries.append(
            {
                "paper_id": panel.get("id"),
                "index": index,
                "title": title,
                "authors": dedupe_preserve_order(authors),
                "subjects": dedupe_preserve_order(subjects),
                "keywords": keywords,
                "summary": summary,
                "session": None,
                "time": None,
                "links": links,
                "scores": {"pdf": pdf_score, "kimi": kimi_score},
                "raw_excerpt": clean_raw_excerpt(panel.get_text(" ", strip=True)),
            }
        )
    return entries


def parse_maincards(soup, base_url: Optional[str]) -> List[dict]:
    entries = []
    for card in soup.select("div.maincard"):
        title_tag = card.select_one(".maincardBody")
        if not title_tag:
            continue
        title = title_tag.get_text(" ", strip=True)
        if not title:
            continue

        authors_text = (card.select_one(".maincardFooter") or title_tag).get_text(
            " ", strip=True
        )
        session_tag = card.select_one(".maincardHeader")

        entry = {
            "paper_id": card.get("id"),
            "index": None,
            "title": title,
            "authors": split_authors(authors_text),
            "subjects": [],
            "keywords": [],
            "summary": None,
            "session": session_tag.get_text(" ", strip=True) if session_tag else None,
            "time": None,
            "links": extract_links(card, base_url),
            "scores": {},
            "raw_excerpt": clean_raw_excerpt(card.get_text(" ", strip=True)),
        }
        entries.append(entry)
    return entries


def parse_ptitles(soup, base_url: Optional[str]) -> List[dict]:
    entries = []
    for dt in soup.select("dt.ptitle"):
        title = dt.get_text(" ", strip=True)
        if not title:
            continue

        dd = dt.find_next_sibling("dd")
        authors = []
        while dd:
            classes = " ".join(dd.get("class", []))
            dd_text = dd.get_text(" ", strip=True)
            if "authors" in classes or "pauthors" in classes or not authors:
                authors = split_authors(dd_text)
                break
            dd = dd.find_next_sibling("dd")

        entry = {
            "paper_id": dt.get("id"),
            "index": None,
            "title": title,
            "authors": authors,
            "subjects": [],
            "keywords": [],
            "summary": None,
            "session": None,
            "time": None,
            "links": extract_links(dt.parent or dt, base_url),
            "scores": {},
            "raw_excerpt": clean_raw_excerpt(
                " ".join(
                    filter(
                        None,
                        [
                            dt.get_text(" ", strip=True),
                            dd.get_text(" ", strip=True) if dd else None,
                        ],
                    )
                )
            ),
        }
        entries.append(entry)
    return entries


def parse_generic_papers(soup, base_url: Optional[str]) -> List[dict]:
    entries = []
    selectors = ["div.paper", "li.paper", "div.paper-item", "div.program-item"]
    for tag in soup.select(",".join(selectors)):
        classes = tag.get("class", [])
        if "panel" in classes and "paper" in classes:
            continue  # handled by dedicated parser

        title_tag = None
        for candidate in ["h1", "h2", "h3", "h4", "h5"]:
            title_tag = tag.find(candidate)
            if title_tag:
                break
        if not title_tag:
            for candidate in [".title", ".paper-title", ".paper_title"]:
                title_tag = tag.select_one(candidate)
                if title_tag:
                    break
        if not title_tag:
            continue

        title = title_tag.get_text(" ", strip=True)
        if not title:
            continue

        authors_tag = None
        for candidate in [".authors", ".paper-authors", ".paper_authors"]:
            authors_tag = tag.select_one(candidate)
            if authors_tag:
                break

        entry = {
            "paper_id": tag.get("id"),
            "index": None,
            "title": title,
            "authors": split_authors(
                authors_tag.get_text(" ", strip=True) if authors_tag else ""
            ),
            "subjects": [],
            "keywords": [],
            "summary": None,
            "session": None,
            "time": None,
            "links": extract_links(tag, base_url),
            "scores": {},
            "raw_excerpt": clean_raw_excerpt(tag.get_text(" ", strip=True)),
        }
        entries.append(entry)

    return entries


def extract_papers(soup) -> List[dict]:
    base_tag = soup.find("base")
    base_url = base_tag["href"] if base_tag and base_tag.get("href") else None

    candidates = []
    for parser in (
        parse_coolpapers_panels,
        parse_maincards,
        parse_ptitles,
        parse_generic_papers,
    ):
        try:
            candidates.extend(parser(soup, base_url))
        except Exception as exc:
            print(f"Parser {parser.__name__} failed: {exc}")

    deduped: Dict[str, dict] = {}
    for item in candidates:
        title_key = (item.get("title") or "").strip().lower()
        if not title_key:
            continue
        if title_key in deduped:
            deduped[title_key] = merge_entries(deduped[title_key], item)
        else:
            deduped[title_key] = item

    papers = list(deduped.values())
    if papers:
        if any(p.get("index") is not None for p in papers):
            return sorted(
                papers,
                key=lambda x: (
                    x.get("index") is None,
                    x.get("index") or 0,
                    x.get("title", "").lower(),
                ),
            )
        return sorted(papers, key=lambda x: x.get("title", "").lower())

    # Fallback: look for blocks with a heading and at least one link.
    for block in soup.find_all(["article", "div", "li"]):
        links = extract_links(block, base_url)
        if not links:
            continue

        header = block.find(["h1", "h2", "h3", "h4", "h5"])
        if not header:
            continue

        title = header.get_text(" ", strip=True)
        if not title:
            continue

        title_key = title.lower()
        if title_key in deduped:
            continue

        deduped[title_key] = {
            "paper_id": block.get("id"),
            "index": None,
            "title": title,
            "authors": split_authors(block.get_text(" ", strip=True).replace(title, "")),
            "subjects": [],
            "keywords": [],
            "summary": None,
            "session": None,
            "time": None,
            "links": links,
            "scores": {},
            "raw_excerpt": clean_raw_excerpt(block.get_text(" ", strip=True)),
        }

    return sorted(deduped.values(), key=lambda x: x["title"].lower())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch extract paper metadata from Cool Papers HTML pages."
    )
    parser.add_argument(
        "--html",
        help="Parse a single HTML file (overrides --dir/--glob).",
    )
    parser.add_argument(
        "--dir",
        default="html",
        help="Directory containing HTML files to parse in batch.",
    )
    parser.add_argument(
        "--glob",
        default="*.html",
        help="Glob for HTML files inside --dir when --html is not provided.",
    )
    parser.add_argument(
        "--outdir",
        default="data",
        help="Directory where JSON outputs are written.",
    )
    return parser.parse_args()


def parse_file(html_path: Path, out_dir: Path) -> dict:
    if not html_path.exists():
        raise FileNotFoundError(f"HTML file not found: {html_path}")

    raw_html = html_path.read_text(encoding="utf-8")
    if not raw_html.strip():
        raise ValueError(f"HTML file is empty: {html_path}")

    soup = BeautifulSoup(raw_html, "html.parser")
    papers = extract_papers(soup)

    output = {
        "source_html": str(html_path),
        "paper_count": len(papers),
        "papers": papers,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{html_path.stem}.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] {html_path.name} -> {out_path.name} ({len(papers)} papers)")
    return output


def main() -> None:
    args = parse_args()
    out_dir = Path(args.outdir)

    if args.html:
        html_files = [Path(args.html)]
    else:
        html_files = sorted(Path(args.dir).glob(args.glob))

    if not html_files:
        raise SystemExit("No HTML files found to parse.")

    for html_path in html_files:
        try:
            parse_file(html_path, out_dir)
        except Exception as exc:  # pragma: no cover - runtime guard
            print(f"[fail] {html_path}: {exc}")


if __name__ == "__main__":
    main()
