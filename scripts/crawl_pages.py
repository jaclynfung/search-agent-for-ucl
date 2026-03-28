from __future__ import annotations

import argparse
import json
import os
import time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


DEFAULT_SEEDS = [
    "https://www.ucl.ac.uk/bartlett/study",
    "https://www.ucl.ac.uk/bartlett/research",
    "https://www.ucl.ac.uk/bartlett/our-schools-and-institutes",
    "https://www.ucl.ac.uk/bartlett/people",
    "https://www.ucl.ac.uk/bartlett/ideas",
    "https://www.ucl.ac.uk/bartlett/engage",
    "https://www.ucl.ac.uk/bartlett/news-and-events",
    "https://www.ucl.ac.uk/bartlett/about",
    "https://www.ucl.ac.uk/bartlett/architecture/about/contact-us",
    "https://www.ucl.ac.uk/bartlett/architecture/study/teaching-staff",
]
ALLOWED_DOMAINS = {"www.ucl.ac.uk", "ucl.ac.uk"}
STORAGE_ROOT = Path(os.getenv("APP_STORAGE_DIR", "storage"))
OUTPUT_PATH = STORAGE_ROOT / "raw" / "ucl_bartlett_pages.jsonl"
ALLOWED_PATH_PREFIXES = (
    "/bartlett/study",
    "/bartlett/research",
    "/bartlett/our-schools-and-institutes",
    "/bartlett/people",
    "/bartlett/ideas",
    "/bartlett/engage",
    "/bartlett/news-and-events",
    "/bartlett/about",
    "/bartlett/architecture",
    "/bartlett/planning",
    "/bartlett/construction",
    "/bartlett/environment-energy-resources",
    "/bartlett/development",
)


def fetch_page(session: requests.Session, url: str, timeout: int) -> dict[str, str] | None:
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else url
    text = " ".join(soup.get_text(separator=" ").split())
    if not text:
        return None

    return {"url": url, "title": title, "content": text[:20000]}


def extract_links(base_url: str, html_text: str) -> list[str]:
    soup = BeautifulSoup(html_text, "html.parser")
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        candidate = urljoin(base_url, anchor["href"])
        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc.lower() not in ALLOWED_DOMAINS:
            continue
        if not any(parsed.path.rstrip("/").startswith(prefix) for prefix in ALLOWED_PATH_PREFIXES):
            continue
        clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        links.append(clean)
    return links


def crawl(max_pages: int, timeout: int, delay_seconds: float) -> list[dict[str, str]]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
        }
    )

    queue = deque(DEFAULT_SEEDS)
    visited: set[str] = set()
    pages: list[dict[str, str]] = []

    while queue and len(pages) < max_pages:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
        except requests.RequestException:
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title and soup.title.string else url
        text = " ".join(soup.get_text(separator=" ").split())
        if text:
            pages.append({"url": url, "title": title, "content": text[:20000]})

        for link in extract_links(url, response.text):
            if link not in visited:
                queue.append(link)

        time.sleep(delay_seconds)

    return pages


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl UCL Bartlett pages for local indexing.")
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--delay-seconds", type=float, default=0.5)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    pages = crawl(max_pages=args.max_pages, timeout=args.timeout, delay_seconds=args.delay_seconds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for page in pages:
            handle.write(json.dumps(page, ensure_ascii=True) + "\n")

    print(f"Wrote {len(pages)} pages to {args.output}")


if __name__ == "__main__":
    main()
