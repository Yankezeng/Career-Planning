from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

from app.services.agent.common.hf_model_loading import quiet_hf_model_load
from app.services.agent.common.model_manager import (
    ModelDownloadError,
    ModelNotAvailableError,
    ensure_model_available,
    is_model_ready,
    load_cross_encoder,
    log_model_config,
)

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import CrossEncoder
    CROSS_ENCODER_AVAILABLE = True
except ImportError:
    CROSS_ENCODER_AVAILABLE = False


class Reranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self.model = None
        self.cross_encoder_available = CROSS_ENCODER_AVAILABLE
        self._loaded = False
        self._load_attempted = False
        self._load_failed = False
        self._enabled = os.environ.get("ENABLE_RAG_RERANKER", "true").lower() in ("1", "true", "yes")

    def _ensure_reranker(self) -> bool:
        if self._loaded:
            return True
        if self._load_attempted and self._load_failed:
            return False
        if not self.cross_encoder_available:
            logger.warning("[Reranker] sentence_transformers.CrossEncoder 不可用，已降级为原始排序")
            self._load_attempted = True
            self._load_failed = True
            return False
        if not self._enabled:
            logger.info("[Reranker] reranker 已通过配置禁用 (ENABLE_RAG_RERANKER=false)")
            self._load_attempted = True
            self._load_failed = True
            return False

        self._load_attempted = True
        try:
            local_dir = os.environ.get("RERANKER_MODEL_DIR", "./models/reranker")
            offline = os.environ.get("HF_HUB_OFFLINE", "false").lower() in ("1", "true", "yes")
            local_only = os.environ.get("HF_MODEL_LOCAL_FILES_ONLY", "false").lower() in ("1", "true", "yes")

            model_path = ensure_model_available(
                repo_id=self.model_name,
                local_dir=local_dir,
                local_files_only=local_only,
                offline=offline,
            )

            with quiet_hf_model_load():
                self.model = load_cross_encoder(model_path)

            self._loaded = True
            self._load_failed = False
            logger.info("[Reranker] CrossEncoder 加载成功: %s", model_path)
            return True
        except (ModelNotAvailableError, ModelDownloadError, ImportError) as exc:
            self._load_failed = True
            self.model = None
            logger.warning("[Reranker] reranker 模型不可用，已降级为原始排序。原因: %s", exc)
            return False
        except Exception as exc:
            self._load_failed = True
            self.model = None
            logger.warning(
                "[Reranker] CrossEncoder 加载异常，已降级为原始排序。原因: %s", exc, exc_info=True,
            )
            return False

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []

        if not self._ensure_reranker():
            return candidates[:top_k]

        try:
            doc_texts = []
            for candidate in candidates:
                content = candidate.get("content") or ""
                metadata = candidate.get("metadata", {})
                title = metadata.get("job_name", "") or metadata.get("title", "")
                if title:
                    doc_texts.append(f"{title}: {content}")
                else:
                    doc_texts.append(content)

            pairs = [(query, doc) for doc in doc_texts]
            scores = self.model.predict(pairs)

            scored_candidates = []
            for idx, candidate in enumerate(candidates):
                scored_candidate = dict(candidate)
                scored_candidate["rerank_score"] = float(scores[idx])
                scored_candidates.append(scored_candidate)

            scored_candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
            return scored_candidates[:top_k]
        except Exception:
            logger.warning("[Reranker] rerank 过程异常，返回原始排序结果", exc_info=True)
            return candidates[:top_k]

    def is_available(self) -> bool:
        if self._loaded and self.model is not None:
            return True
        return self._ensure_reranker()


@lru_cache(maxsize=4)
def get_reranker(model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> Reranker:
    log_model_config()
    return Reranker(model_name)
