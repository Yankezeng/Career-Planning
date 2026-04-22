from __future__ import annotations

from functools import lru_cache
from typing import Any
from collections import defaultdict

try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False

from app.services.vector_search_service import VectorSearchService


RRF_K = 60


class HybridSearchEngine:
    def __init__(self, vector_search_service: VectorSearchService | None = None):
        self.vector_search_service = vector_search_service or VectorSearchService()
        self.bm25_available = BM25_AVAILABLE
        self.corpus_cache = {}
        self.bm25_cache = {}

    def search(
        self,
        query: str,
        top_k: int = 10,
        vector_weight: float = 0.6,
        bm25_weight: float = 0.4,
    ) -> list[dict[str, Any]]:
        query = query.strip()
        if not query:
            return []

        vector_results = self._vector_search(query, top_k * 2)

        bm25_results = []
        if self.bm25_available:
            bm25_results = self._bm25_search(query, top_k * 2)

        if not vector_results and not bm25_results:
            return []

        fused = self._rrf_fusion(
            vector_results,
            bm25_results,
            vector_weight=vector_weight,
            bm25_weight=bm25_weight,
        )

        return fused[:top_k]

    def _vector_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        try:
            hits = self.vector_search_service.search(query, top_k=top_k)
            results = []
            for idx, hit in enumerate(hits or []):
                results.append({
                    "id": hit.get("id") or f"vec_{idx}",
                    "score": hit.get("score", 0.0),
                    "content": hit.get("content", ""),
                    "metadata": hit.get("metadata", {}),
                    "source": "vector",
                })
            return results
        except Exception:
            return []

    def _bm25_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        if not self.bm25_available:
            return []

        try:
            corpus = self._get_corpus()
            if not corpus:
                return []

            bm25 = BM25Okapi(corpus["documents"])
            tokenized_query = query.lower().split()

            scores = bm25.get_scores(tokenized_query)

            results = []
            for idx, score in enumerate(scores):
                if score > 0:
                    results.append({
                        "id": corpus["ids"][idx],
                        "score": float(score),
                        "content": corpus["documents"][idx],
                        "metadata": corpus["metadatas"][idx] if corpus.get("metadatas") else {},
                        "source": "bm25",
                    })

            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]

        except Exception:
            return []

    def _rrf_fusion(
        self,
        vector_results: list[dict[str, Any]],
        bm25_results: list[dict[str, Any]],
        vector_weight: float = 0.6,
        bm25_weight: float = 0.4,
    ) -> list[dict[str, Any]]:
        scores = defaultdict(float)
        doc_info = {}

        for rank, result in enumerate(vector_results):
            doc_id = result["id"]
            rrf_score = 1.0 / (RRF_K + rank + 1)
            scores[doc_id] += vector_weight * rrf_score
            doc_info[doc_id] = result

        for rank, result in enumerate(bm25_results):
            doc_id = result["id"]
            rrf_score = 1.0 / (RRF_K + rank + 1)
            scores[doc_id] += bm25_weight * rrf_score
            if doc_id not in doc_info:
                doc_info[doc_id] = result

        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        fused_results = []
        for doc_id, fused_score in sorted_docs:
            result = dict(doc_info[doc_id])
            result["fused_score"] = round(fused_score, 4)
            result["original_score"] = result.get("score", 0)
            fused_results.append(result)

        return fused_results

    def _get_corpus(self) -> dict[str, list]:
        if "default" in self.corpus_cache:
            return self.corpus_cache["default"]

        try:
            job_docs = []
            job_ids = []
            job_metas = []

            from app.core.database import SessionLocal
            from app.models.job import Job

            db = SessionLocal()
            try:
                jobs = db.query(Job).filter(Job.deleted.is_(False)).limit(1000).all()
                for job in jobs:
                    doc_text = f"{job.name} {job.description or ''} {job.requirements or ''} {job.category or ''}"
                    job_docs.append(doc_text.lower())
                    job_ids.append(f"job_{job.id}")
                    job_metas.append({
                        "job_name": job.name,
                        "category": job.category,
                        "description": job.description,
                    })
            finally:
                db.close()

            if job_docs:
                self.corpus_cache["default"] = {
                    "documents": job_docs,
                    "ids": job_ids,
                    "metadatas": job_metas,
                }
                return self.corpus_cache["default"]

        except Exception:
            pass

        return {"documents": [], "ids": [], "metadatas": []}

    def index_document(self, doc_id: str, content: str, metadata: dict | None = None):
        self.corpus_cache.clear()

    def clear_cache(self):
        self.corpus_cache.clear()
        self.bm25_cache.clear()


@lru_cache(maxsize=1)
def get_hybrid_search_engine() -> HybridSearchEngine:
    return HybridSearchEngine()
