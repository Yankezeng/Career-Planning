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
    load_sentence_transformer,
    log_model_config,
)
from app.services.llm_service import get_llm_service

logger = logging.getLogger(__name__)

INTENT_TEMPLATES = {
    "small_talk": [
        "你好", "hi", "hello", "在吗", "谢谢", "好的", "ok", "收到", "继续", "嗯", "在",
        "早上好", "晚上好", "晚安", "辛苦了", "好的谢谢", "没问题"
    ],
    "ask_advice": [
        "我应该怎么做", "怎么办", "如何选择", "给我建议", "有什么建议",
        "我该准备什么", "怎么做比较好", "有什么推荐", "方向是什么",
        "我适合什么", "能帮我分析一下吗", "有什么想法"
    ],
    "execute": [
        "帮我生成", "生成一个", "创建", "执行", "做一下",
        "生成报告", "生成画像", "生成匹配", "生成路径",
        "优化简历", "投递简历", "开始执行"
    ],
    "compare": [
        "对比", "比较", "差异", "区别", "哪个好",
        "有什么不同", "哪个更适合", "推荐哪个"
    ],
    "follow_up": [
        "继续", "展开", "细说", "那", "再看", "再分析", "接着",
        "然后呢", "详细说说", "展开说说", "继续刚才的"
    ],
    "switch_skill": [
        "切换技能", "换技能", "用技能", "切到", "换一个功能",
        "换个模式", "换一个技能"
    ],
    "clarify": [
        "是什么", "什么意思", "解释一下", "详细说明",
        "具体是什么", "比如什么"
    ],
    "ask_fact": [
        "当前", "现在", "有多少", "有没有", "在吗",
        "我的简历呢", "我的岗位呢", "匹配结果呢"
    ],
    "refine": [
        "再优化", "润色", "改写", "精简", "细化",
        "再详细点", "再完善一下", "调整一下"
    ],
    "planning": [
        "计划", "路线", "步骤", "优先", "怎么安排",
        "时间规划", "阶段安排", "具体步骤"
    ],
}

DEFAULT_CONFIDENCE_THRESHOLD = 0.65


class IntentClassifier:
    def __init__(self):
        self.llm_service = get_llm_service()
        self.embedding_model = None
        self._embedding_loaded = False
        self._embedding_load_attempted = False
        self._embedding_failed = False
        self.intent_templates = INTENT_TEMPLATES
        self._template_embeddings: dict[str, list[Any]] = {}
        self._template_embeddings_initialized = False
        self.confidence_threshold = DEFAULT_CONFIDENCE_THRESHOLD
        self._enabled = os.environ.get("ENABLE_INTENT_EMBEDDING", "true").lower() in ("1", "true", "yes")

    def _ensure_embedding_model(self) -> bool:
        if self._embedding_loaded:
            return True
        if self._embedding_load_attempted and self._embedding_failed:
            return False
        if not self._enabled:
            logger.info("[IntentClassifier] embedding 已通过配置禁用 (ENABLE_INTENT_EMBEDDING=false)")
            return False

        self._embedding_load_attempted = True
        try:
            model_name = os.environ.get(
                "EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            )
            local_dir = os.environ.get("EMBEDDING_MODEL_DIR", "./models/embedding")
            offline = os.environ.get("HF_HUB_OFFLINE", "false").lower() in ("1", "true", "yes")
            local_only = os.environ.get("HF_MODEL_LOCAL_FILES_ONLY", "false").lower() in ("1", "true", "yes")

            model_path = ensure_model_available(
                repo_id=model_name,
                local_dir=local_dir,
                local_files_only=local_only,
                offline=offline,
            )

            with quiet_hf_model_load():
                self.embedding_model = load_sentence_transformer(model_path)

            self._embedding_loaded = True
            self._embedding_failed = False
            logger.info("[IntentClassifier] embedding 模型加载成功: %s", model_path)
            return True
        except (ModelNotAvailableError, ModelDownloadError, ImportError) as exc:
            self._embedding_failed = True
            self.embedding_model = None
            logger.warning(
                "[IntentClassifier] embedding 模型不可用，已降级为规则分类。原因: %s", exc
            )
            return False
        except Exception as exc:
            self._embedding_failed = True
            self.embedding_model = None
            logger.warning(
                "[IntentClassifier] embedding 模型加载异常，已降级为规则分类。原因: %s", exc,
                exc_info=True,
            )
            return False

    def _ensure_template_embeddings(self) -> None:
        if self._template_embeddings_initialized:
            return
        if not self._ensure_embedding_model():
            self._template_embeddings_initialized = True
            return

        self._template_embeddings_initialized = True
        if not self.embedding_model:
            return

        try:
            for intent, templates in self.intent_templates.items():
                try:
                    embeddings = self.embedding_model.encode(templates)
                    self._template_embeddings[intent] = list(embeddings)
                except Exception as exc:
                    logger.warning("[IntentClassifier] 意图 '%s' 模板嵌入失败，跳过: %s", intent, exc)
            logger.info("[IntentClassifier] 模板嵌入向量初始化完成，共 %d 个意图", len(self._template_embeddings))
        except Exception as exc:
            logger.warning("[IntentClassifier] 模板嵌入初始化失败，将仅使用规则分类: %s", exc)
            self._template_embeddings = {}

    def classify(self, message: str, session_state: dict[str, Any] | None = None) -> dict[str, Any]:
        if not message or not message.strip():
            return {"intent": "clarify_required", "confidence": 1.0, "reason": "empty_message"}

        text = message.strip().lower().replace(" ", "")

        if self._is_small_talk(text):
            session_state = session_state or {}
            if text in {"继续", "展开"} and session_state.get("last_analysis_focus"):
                return {"intent": "follow_up", "confidence": 0.9, "reason": "continue_previous_focus"}
            return {"intent": "small_talk", "confidence": 0.95, "reason": "light_message"}

        self._ensure_template_embeddings()
        embedding_result = self._embedding_classify(text)
        if embedding_result and embedding_result["confidence"] >= self.confidence_threshold:
            return embedding_result

        return self._rule_based_classify(text, session_state)

    def _embedding_classify(self, text: str) -> dict[str, Any] | None:
        if not self.embedding_model or not self._template_embeddings:
            return None

        try:
            message_embedding = self.embedding_model.encode(text)
        except Exception:
            return None

        best_intent = None
        best_score = 0.0
        for intent, embeddings in self._template_embeddings.items():
            for template_embedding in embeddings:
                score = self._cosine_similarity(message_embedding, template_embedding)
                if score > best_score:
                    best_intent = intent
                    best_score = score

        if not best_intent:
            return None

        return {"intent": best_intent, "confidence": best_score, "reason": "embedding_similarity"}

    def _cosine_similarity(self, left: Any, right: Any) -> float:
        left_values = self._as_float_list(left)
        right_values = self._as_float_list(right)
        if not left_values or not right_values or len(left_values) != len(right_values):
            return 0.0

        dot_product = sum(lv * rv for lv, rv in zip(left_values, right_values))
        left_norm = sum(v * v for v in left_values) ** 0.5
        right_norm = sum(v * v for v in right_values) ** 0.5
        if not left_norm or not right_norm:
            return 0.0
        return dot_product / (left_norm * right_norm)

    def _as_float_list(self, vector: Any) -> list[float]:
        if hasattr(vector, "tolist"):
            vector = vector.tolist()
        if vector and isinstance(vector[0], list):
            vector = vector[0]
        return [float(v) for v in vector]

    def _rule_based_classify(self, text: str, session_state: dict[str, Any] | None = None) -> dict[str, Any]:
        text = text.lower().replace(" ", "")

        if any(token in text for token in ["切换技能", "换技能", "用技能", "切到"]):
            return {"intent": "switch_skill", "confidence": 0.85, "reason": "skill_switch"}
        if any(token in text for token in ["对比", "比较", "vs", "差异", "区别"]):
            return {"intent": "compare", "confidence": 0.85, "reason": "compare"}
        if any(token in text for token in ["执行", "生成", "创建", "优化", "投递", "设为默认", "开始"]):
            return {"intent": "execute", "confidence": 0.8, "reason": "action_request"}
        if any(token in text for token in ["计划", "路线", "步骤", "优先", "怎么安排"]):
            return {"intent": "planning", "confidence": 0.8, "reason": "planning"}
        if any(token in text for token in ["建议", "怎么办", "如何", "怎么做", "缺什么"]):
            return {"intent": "ask_advice", "confidence": 0.75, "reason": "advice"}
        if any(token in text for token in ["是什么", "当前", "多少", "有没有", "吗"]):
            return {"intent": "ask_fact", "confidence": 0.75, "reason": "fact_question"}
        if any(token in text for token in ["再优化", "润色", "改写", "精简", "细化"]):
            return {"intent": "refine", "confidence": 0.8, "reason": "refine"}
        if any(token in text for token in ["继续", "展开", "细说", "那", "再看", "再分析", "接着", "然后呢"]):
            return {"intent": "follow_up", "confidence": 0.85, "reason": "follow_up"}

        return {"intent": "clarify_required", "confidence": 0.0, "reason": "no_intent_match"}

    def _is_small_talk(self, text: str) -> bool:
        small_talk_tokens = {
            "你好", "hi", "hello", "在吗", "谢谢", "好的", "ok", "收到", "继续", "嗯", "在",
            "早上好", "晚上好", "晚安", "辛苦了", "好的谢谢", "没问题", "好", "行", "收到"
        }
        text_normalized = text.lower().replace(" ", "")
        if text_normalized in small_talk_tokens:
            return True
        if len(text_normalized) <= 4 and any(t in text_normalized for t in small_talk_tokens):
            return True
        return False

    def set_threshold(self, threshold: float):
        self.confidence_threshold = threshold

    def add_intent_template(self, intent: str, templates: list[str]):
        if intent in self.intent_templates:
            self.intent_templates[intent].extend(templates)
        else:
            self.intent_templates[intent] = templates
        if self.embedding_model and self._embedding_loaded and self._template_embeddings_initialized:
            try:
                embeddings = self.embedding_model.encode(templates)
                self._template_embeddings.setdefault(intent, []).extend(list(embeddings))
            except Exception as exc:
                logger.warning("[IntentClassifier] 动态模板嵌入失败 (intent=%s): %s", intent, exc)


@lru_cache(maxsize=1)
def get_intent_classifier() -> IntentClassifier:
    log_model_config()
    return IntentClassifier()
