"""Hybrid retrieval: BM25 keyword match + FAISS semantic search, fused with RRF.

Exact error strings and case numbers are boosted so factory-floor wording wins.
"""

from __future__ import annotations

import pickle
import re
from pathlib import Path
from typing import Any

import numpy as np
from rank_bm25 import BM25Okapi

from knowledge import ROOT, all_cases

INDEX_DIR = ROOT / "indexes"
EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
RRF_K = 60
MATCH_THRESHOLD = 0.028
TOKEN_RE = re.compile(r"[a-z0-9$._/-]+", re.I)
CASE_NUM_RE = re.compile(r"\b(?:case\s*)?0*([1-9]\d?)\b", re.I)
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is",
    "it", "of", "on", "or", "that", "the", "this", "to", "was", "with", "you",
    "your", "will", "not", "no", "if", "then", "than",
}


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for tok in TOKEN_RE.findall(text):
        lowered = tok.lower()
        if lowered in STOPWORDS:
            continue
        if lowered.isdigit() and len(lowered) < 3:
            continue
        tokens.append(lowered)
    return tokens


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


class HybridRetriever:
    def __init__(self) -> None:
        self.cases = all_cases()
        self._bm25 = BM25Okapi([_tokenize(c["search_text"]) for c in self.cases])
        self._model = None
        self._index = None
        self._embeddings: np.ndarray | None = None
        self._ensure_dense_index()

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(EMBED_MODEL_NAME)
        return self._model

    def _ensure_dense_index(self) -> None:
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        embed_path = INDEX_DIR / "case_embeddings.npy"
        meta_path = INDEX_DIR / "index_meta.pkl"
        expected_ids = [c["case_id"] for c in self.cases]

        if embed_path.exists() and meta_path.exists():
            meta = pickle.loads(meta_path.read_bytes())
            if meta.get("model") == EMBED_MODEL_NAME and meta.get("case_ids") == expected_ids:
                self._embeddings = np.load(embed_path)
                self._build_faiss(self._embeddings)
                return

        model = self._load_model()
        vectors = model.encode(
            [c["search_text"] for c in self.cases],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).astype(np.float32)
        self._embeddings = vectors
        np.save(embed_path, vectors)
        meta_path.write_bytes(
            pickle.dumps({"model": EMBED_MODEL_NAME, "case_ids": expected_ids})
        )
        self._build_faiss(vectors)

    def _build_faiss(self, vectors: np.ndarray) -> None:
        try:
            import faiss

            index = faiss.IndexFlatIP(vectors.shape[1])
            index.add(vectors)
            self._index = index
        except Exception:
            self._index = None

    def _faiss_ranks(self, query: str, top_k: int) -> list[tuple[int, float]]:
        model = self._load_model()
        qvec = model.encode(
            [query], convert_to_numpy=True, normalize_embeddings=True
        ).astype(np.float32)
        if self._index is not None:
            import faiss

            scores, idxs = self._index.search(qvec, top_k)
            return [
                (int(i), float(s))
                for i, s in zip(idxs[0], scores[0])
                if i >= 0
            ]
        assert self._embeddings is not None
        sims = (self._embeddings @ qvec[0]).astype(np.float64)
        order = np.argsort(-sims)[:top_k]
        return [(int(i), float(sims[i])) for i in order]

    def _bm25_ranks(self, query: str, top_k: int) -> list[tuple[int, float]]:
        scores = np.array(self._bm25.get_scores(_tokenize(query)), dtype=np.float64)
        order = np.argsort(-scores)[:top_k]
        return [(int(i), float(scores[i])) for i in order if scores[i] > 0]

    def _rrf(
        self,
        ranked_lists: list[list[tuple[int, float]]],
        weights: list[float],
    ) -> dict[int, float]:
        fused: dict[int, float] = {}
        for ranked, weight in zip(ranked_lists, weights):
            for rank, (idx, _) in enumerate(ranked, start=1):
                fused[idx] = fused.get(idx, 0.0) + weight * (1.0 / (RRF_K + rank))
        return fused

    def _exact_message_hits(self, query: str) -> list[tuple[int, float]]:
        q = _normalize(query)
        qt = set(_tokenize(q))
        hits: list[tuple[int, float]] = []
        for i, case in enumerate(self.cases):
            best = 0.0
            for message in case.get("exact_messages", []):
                m = _normalize(message)
                if not m:
                    continue
                if q == m or m in q:
                    best = max(best, 1.0)
                    continue
                if len(q) >= 16 and q in m:
                    best = max(best, 0.94)
                    continue
                content = {tok for tok in _tokenize(m) if len(tok) > 3 or tok in {"$$", "iqc", "erp", "pr"}}
                if content and content <= qt:
                    best = max(best, 0.9)
            if best:
                hits.append((i, best))
        hits.sort(key=lambda item: item[1], reverse=True)
        return hits

    def _case_number_hits(self, query: str) -> list[tuple[int, float]]:
        q = query.strip().lower()
        explicit = re.search(r"\bcase\s*0*([1-9]\d?)\b", q)
        if not explicit:
            return []
        number = int(explicit.group(1))
        if 1 <= number <= 52:
            for i, case in enumerate(self.cases):
                if int(case["case_number"]) == number:
                    return [(i, 1.0)]
        return []

    def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        query = query.strip()
        if not query:
            return []

        top_n = max(top_k, 8)
        case_hits = self._case_number_hits(query)
        exact_hits = self._exact_message_hits(query)
        bm25_hits = self._bm25_ranks(query, top_n)
        faiss_hits = self._faiss_ranks(query, top_n)

        fused = self._rrf(
            [case_hits, exact_hits, bm25_hits, faiss_hits],
            weights=[4.0, 3.5, 1.2, 1.0],
        )
        if not fused:
            return []

        ordered = sorted(fused.items(), key=lambda item: item[1], reverse=True)
        best_score = ordered[0][1]
        results: list[dict[str, Any]] = []
        for idx, score in ordered[:top_k]:
            case = dict(self.cases[idx])
            case["score"] = round(float(score), 6)
            case["confident"] = score >= MATCH_THRESHOLD or bool(case_hits) or bool(exact_hits)
            results.append(case)

        # No exact/case hit and a weak fused score: treat as not found.
        if not case_hits and not exact_hits and best_score < MATCH_THRESHOLD:
            return []
        if results and not results[0]["confident"]:
            return []
        return results


_retriever: HybridRetriever | None = None


def get_retriever() -> HybridRetriever:
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever()
    return _retriever
