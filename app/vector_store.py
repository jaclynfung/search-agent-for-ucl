from __future__ import annotations

import json
import os
import pickle
from pathlib import Path
from typing import Any

try:
    import faiss
except ImportError:  # pragma: no cover
    faiss = None


BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_ROOT = Path(os.getenv("APP_STORAGE_DIR", str(BASE_DIR / "storage")))
INDEX_DIR = STORAGE_ROOT / "faiss"
INDEX_PATH = INDEX_DIR / "ucl_bartlett.index"
METADATA_PATH = INDEX_DIR / "metadata.json"
VECTORIZER_PATH = INDEX_DIR / "vectorizer.pkl"


class BartlettVectorStore:
    def __init__(self) -> None:
        self._loaded = False
        self._index = None
        self._metadata: list[dict[str, Any]] = []
        self._vectorizer = None

    def search(self, query: str, entity: str | None, top_k: int = 3) -> dict[str, Any] | None:
        if faiss is None:
            return None

        self._load()
        if self._index is None or self._vectorizer is None or not self._metadata:
            return None

        effective_query = query.strip() or entity or ""
        if not effective_query:
            return None

        vector = self._vectorizer.transform([effective_query]).toarray().astype("float32")
        faiss.normalize_L2(vector)
        distances, indices = self._index.search(vector, top_k)

        hits: list[dict[str, Any]] = []
        for score, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self._metadata):
                continue
            item = self._metadata[idx]
            hits.append(
                {
                    "score": float(score),
                    "title": item["title"],
                    "url": item["url"],
                    "content": item["content"],
                }
            )

        if not hits:
            return None

        top_hit = hits[0]
        answer = f"{top_hit['title']}: {top_hit['content'][:280].strip()}"
        return {
            "answer": answer,
            "sources": [hit["url"] for hit in hits],
            "confidence": self._score_to_confidence(top_hit["score"]),
        }

    def _load(self) -> None:
        if self._loaded:
            return

        self._loaded = True
        if not INDEX_PATH.exists() or not METADATA_PATH.exists() or not VECTORIZER_PATH.exists():
            return

        self._index = faiss.read_index(str(INDEX_PATH))
        self._metadata = json.loads(METADATA_PATH.read_text())
        with VECTORIZER_PATH.open("rb") as handle:
            self._vectorizer = pickle.load(handle)

    def _score_to_confidence(self, score: float) -> str:
        if score >= 0.6:
            return "high"
        if score >= 0.3:
            return "medium"
        return "low"
