from __future__ import annotations

import argparse
import json
import os
import pickle
from pathlib import Path

import faiss
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


STORAGE_ROOT = Path(os.getenv("APP_STORAGE_DIR", "storage"))
RAW_PATH = STORAGE_ROOT / "raw" / "ucl_bartlett_pages.jsonl"
INDEX_DIR = STORAGE_ROOT / "faiss"
INDEX_PATH = INDEX_DIR / "ucl_bartlett.index"
METADATA_PATH = INDEX_DIR / "metadata.json"
VECTORIZER_PATH = INDEX_DIR / "vectorizer.pkl"


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    step = max(chunk_size - overlap, 1)
    for start in range(0, len(words), step):
        chunk = words[start : start + chunk_size]
        if not chunk:
            continue
        chunks.append(" ".join(chunk))
        if start + chunk_size >= len(words):
            break
    return chunks


def load_documents(path: Path, chunk_size: int, overlap: int) -> list[dict[str, str]]:
    documents: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            page = json.loads(line)
            for chunk in chunk_text(page["content"], chunk_size=chunk_size, overlap=overlap):
                documents.append(
                    {
                        "title": page["title"],
                        "url": page["url"],
                        "content": chunk,
                    }
                )
    return documents


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a FAISS index for UCL Bartlett pages.")
    parser.add_argument("--input", type=Path, default=RAW_PATH)
    parser.add_argument("--chunk-size", type=int, default=180)
    parser.add_argument("--overlap", type=int, default=40)
    args = parser.parse_args()

    documents = load_documents(args.input, chunk_size=args.chunk_size, overlap=args.overlap)
    if not documents:
        raise SystemExit("No documents found. Run the crawler first.")

    corpus = [doc["content"] for doc in documents]
    vectorizer = TfidfVectorizer(stop_words="english", max_features=4096)
    matrix = vectorizer.fit_transform(corpus).toarray().astype("float32")
    faiss.normalize_L2(matrix)

    index = faiss.IndexFlatIP(matrix.shape[1])
    index.add(matrix)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_PATH))
    METADATA_PATH.write_text(json.dumps(documents, ensure_ascii=True, indent=2))
    with VECTORIZER_PATH.open("wb") as handle:
        pickle.dump(vectorizer, handle)

    print(f"Built FAISS index with {len(documents)} chunks at {INDEX_PATH}")


if __name__ == "__main__":
    main()
