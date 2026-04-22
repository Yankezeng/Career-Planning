from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.services.agent.common.rag.query_rewriter import QueryRewriter, get_query_rewriter
from app.services.agent.common.rag.hybrid_search import HybridSearchEngine, get_hybrid_search_engine
from app.services.agent.common.rag.reranker import Reranker, get_reranker


class EnhancedRAG:
    def __init__(self):
        self.query_rewriter = get_query_rewriter()
        self.hybrid_search = get_hybrid_search_engine()
        self.reranker = get_reranker()

    def search(
        self,
        query: str,
        top_k: int = 10,
        use_rerank: bool = True,
        use_hybrid: bool = True,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = context or {}

        rewrite_result = self.query_rewriter.rewrite(query, context)
        rewritten_query = rewrite_result.get("rewritten_query", query)

        if use_hybrid:
            candidates = self.hybrid_search.search(
                rewritten_query,
                top_k=top_k * 2,
            )
        else:
            from app.services.vector_search_service import VectorSearchService
            vector_service = VectorSearchService()
            try:
                hits = vector_service.search(rewritten_query, top_k=top_k * 2)
                candidates = []
                for idx, hit in enumerate(hits or []):
                    candidates.append({
                        "id": hit.get("id") or f"vec_{idx}",
                        "score": hit.get("score", 0.0),
                        "content": hit.get("content", ""),
                        "metadata": hit.get("metadata", {}),
                        "source": "vector",
                    })
            except Exception:
                candidates = []

        reranker_was_available = False
        if use_rerank and candidates:
            reranker_was_available = self.reranker.is_available()
            if reranker_was_available:
                final_results = self.reranker.rerank(
                    query,
                    candidates,
                    top_k=top_k,
                )
            else:
                final_results = candidates[:top_k]
        else:
            final_results = candidates[:top_k]

        retrieval_chunks = self._format_retrieval_chunks(final_results)

        return {
            "query": query,
            "rewritten_query": rewritten_query,
            "rewrite_strategy": rewrite_result.get("strategy", "none"),
            "expansions": rewrite_result.get("expansions", []),
            "results": final_results,
            "retrieval_chunks": retrieval_chunks,
            "total_found": len(candidates),
            "reranked": reranker_was_available,
            "hybrid_search": use_hybrid,
        }

    def _format_retrieval_chunks(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        chunks = []
        for item in results:
            metadata = item.get("metadata", {})
            content = item.get("content", "")

            snippet = content[:200].replace("\n", " ").strip() if content else ""

            chunks.append({
                "id": item.get("id", ""),
                "job_name": metadata.get("job_name", "宀椾綅淇℃伅"),
                "company_name": metadata.get("company_name", ""),
                "score": item.get("fused_score") or item.get("score") or item.get("rerank_score", 0),
                "snippet": snippet,
                "industry": metadata.get("industry", ""),
                "source": item.get("source", "unknown"),
            })

        return chunks

    def set_rerank_model(self, model_name: str):
        self.reranker = get_reranker(model_name)

    def set_hybrid_weights(self, vector_weight: float, bm25_weight: float):
        self.hybrid_search = get_hybrid_search_engine()


@lru_cache(maxsize=1)
def get_enhanced_rag() -> EnhancedRAG:
    return EnhancedRAG()
