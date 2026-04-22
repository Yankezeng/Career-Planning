from __future__ import annotations

from app.core.project_paths import PROJECT_ROOT  # noqa: F401


class _UnavailableKnowledgeBase:
    backend_name = "unavailable"

    def __init__(self, reason: str = ""):
        self.reason = reason

    def search(self, query: str, top_k: int = 5):
        return []

    def list_documents(self, limit: int = 5000):
        return []

    def describe(self):
        return {"backend": self.backend_name, "reason": self.reason}

    def count_documents(self) -> int:
        return 0

    def get_document_by_id(self, doc_id: str):
        return None


try:
    from app.services.knowledge.job_kb_milvus import MilvusJobKnowledgeBase as _MilvusJobKnowledgeBase
except Exception as exc:  # pragma: no cover - depends on local env native deps
    _MILVUS_IMPORT_ERROR = str(exc)
    _MilvusJobKnowledgeBase = None
else:
    _MILVUS_IMPORT_ERROR = ""


class VectorSearchService:
    """Milvus-backed vector search service for the job knowledge base."""

    def __init__(self):
        if _MilvusJobKnowledgeBase is None:
            self.knowledge_base = _UnavailableKnowledgeBase(reason=_MILVUS_IMPORT_ERROR)
        else:
            try:
                self.knowledge_base = _MilvusJobKnowledgeBase()
            except Exception as exc:  # pragma: no cover - runtime backend init failure
                self.knowledge_base = _UnavailableKnowledgeBase(reason=str(exc))
        self.backend_name = getattr(self.knowledge_base, "backend_name", "unavailable")

    def search(self, query: str, top_k: int = 5):
        try:
            return self.knowledge_base.search(query=query, top_k=top_k)
        except Exception:
            return []

    def list_documents(self, limit: int = 5000):
        try:
            return self.knowledge_base.list_documents(limit=limit)
        except Exception:
            return []

    def describe(self):
        return self.knowledge_base.describe()

    def count_documents(self) -> int:
        try:
            return int(self.knowledge_base.count_documents() or 0)
        except Exception:
            return 0

    def get_document_by_id(self, doc_id: str):
        try:
            return self.knowledge_base.get_document_by_id(doc_id)
        except Exception:
            return None
