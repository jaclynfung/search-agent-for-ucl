from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl UCL Bartlett pages and rebuild the FAISS index.")
    parser.add_argument("--max-pages", type=int, default=25)
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--delay-seconds", type=float, default=0.5)
    parser.add_argument("--chunk-size", type=int, default=180)
    parser.add_argument("--overlap", type=int, default=40)
    args = parser.parse_args()

    crawl_cmd = [
        sys.executable,
        "scripts/crawl_pages.py",
        "--max-pages",
        str(args.max_pages),
        "--timeout",
        str(args.timeout),
        "--delay-seconds",
        str(args.delay_seconds),
    ]
    build_cmd = [
        sys.executable,
        "scripts/build_faiss_index.py",
        "--chunk-size",
        str(args.chunk_size),
        "--overlap",
        str(args.overlap),
    ]

    subprocess.run(crawl_cmd, check=True)
    subprocess.run(build_cmd, check=True)


if __name__ == "__main__":
    main()
