from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from sqlalchemy import func, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.database import engine
from app.models.auth import EnterpriseProfile, Role, User
from app.models.career import LLMRequestLog, Report, ResumeDelivery, SystemConfig
from app.models.job import Job, JobMatchResult
from app.models.student import Student, StudentAttachment, StudentProfile
from app.services.llm_service import get_llm_service
from app.services.quality_evaluation_service import QualityEvaluationService
from app.services.vector_search_service import VectorSearchService


class SystemMonitorService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.vector_service = VectorSearchService()

    def get_control_center(self) -> dict[str, Any]:
        business_db = self._business_db_status()
        vector_db = self._vector_db_status()
        role_distribution = self._role_distribution()
        counts = self._system_counts()

        return {
            "runtime": {
                "project_name": self.settings.PROJECT_NAME,
                "api_prefix": self.settings.API_V1_STR,
                "llm_provider": self.settings.LLM_PROVIDER,
                "langchain_model": self.settings.LANGCHAIN_MODEL,
                "upload_dir": str(self.settings.upload_path),
                "pdf_dir": str(self.settings.pdf_path),
            },
            "business_db": business_db,
            "vector_db": vector_db,
            "counts": counts,
            "role_distribution": role_distribution,
            "highlights": self._highlights(counts, business_db, vector_db),
            "crm_dashboard": self._crm_dashboard(),
            "quality_panel": QualityEvaluationService(self.db).evaluate(),
        }

    def get_llm_overview(self) -> dict[str, Any]:
        monitored_models = self._llm_monitored_models()
        primary_model = monitored_models[0] if monitored_models else {"provider": "mock", "model_name": "mock", "api_base_url": "", "has_api_key": True}
        now = datetime.now(timezone.utc)
        day_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

        base_query = self.db.query(LLMRequestLog).filter(LLMRequestLog.deleted.is_(False))
        today_query = base_query.filter(LLMRequestLog.created_at >= day_start)
        today_request_count = today_query.count()
        today_success_count = today_query.filter(LLMRequestLog.status == "success").count()
        today_failed_count = today_query.filter(LLMRequestLog.status == "failed").count()
        today_total_tokens = int(
            today_query.with_entities(func.coalesce(func.sum(LLMRequestLog.total_tokens), 0)).scalar() or 0
        )
        avg_latency = today_query.with_entities(func.avg(LLMRequestLog.latency_ms)).scalar()
        avg_latency_ms = round(float(avg_latency), 2) if avg_latency is not None else 0.0

        last_success = (
            base_query.filter(LLMRequestLog.status == "success")
            .order_by(LLMRequestLog.created_at.desc(), LLMRequestLog.id.desc())
            .first()
        )
        last_failed = (
            base_query.filter(LLMRequestLog.status == "failed")
            .order_by(LLMRequestLog.created_at.desc(), LLMRequestLog.id.desc())
            .first()
        )

        model_overviews = [
            self._build_model_overview(
                model_config=model_config,
                base_query=base_query,
                day_start=day_start,
            )
            for model_config in monitored_models
        ]
        connection_status = self._merge_connection_status([str(item.get("connection_status") or "") for item in model_overviews])

        success_rate = round((today_success_count / today_request_count) * 100, 2) if today_request_count else 0.0

        return {
            "provider": primary_model["provider"],
            "model_name": primary_model["model_name"],
            "api_base_url": primary_model["api_base_url"],
            "connection_status": connection_status,
            "last_success_at": last_success.created_at.isoformat(timespec="seconds") if last_success and last_success.created_at else "",
            "last_error_at": last_failed.created_at.isoformat(timespec="seconds") if last_failed and last_failed.created_at else "",
            "last_error_message": (last_failed.error_message or "") if last_failed else "",
            "today_request_count": today_request_count,
            "today_success_count": today_success_count,
            "today_failed_count": today_failed_count,
            "today_total_tokens": today_total_tokens,
            "avg_latency_ms": avg_latency_ms,
            "success_rate": success_rate,
            "models": model_overviews,
            "note": "当前展示的是系统内记录的模型调用统计，不等同于厂商控制台总账单额度。",
        }

    def get_llm_usage_trend(self, mode: str = "24h") -> dict[str, Any]:
        monitored_models = self._llm_monitored_models()
        model_order = [str(item.get("model_name") or "") for item in monitored_models if str(item.get("model_name") or "")]
        normalized_mode = str(mode or "24h").lower()
        now = datetime.now(timezone.utc)
        by_day = normalized_mode in {"7d", "day", "daily"}

        def new_bucket() -> dict[str, dict[str, float | int]]:
            return {
                label: {"request_count": 0, "total_tokens": 0, "failed_count": 0, "latency_sum": 0.0, "latency_count": 0}
                for label in labels
            }

        def touch_bucket(cell: dict[str, float | int], *, status: str, total_tokens: int, latency_ms: float | None) -> None:
            cell["request_count"] += 1
            cell["total_tokens"] += int(total_tokens or 0)
            if str(status or "") == "failed":
                cell["failed_count"] += 1
            if latency_ms is not None:
                cell["latency_sum"] += float(latency_ms)
                cell["latency_count"] += 1

        if by_day:
            start = now - timedelta(days=6)
            labels = [(start + timedelta(days=index)).strftime("%m-%d") for index in range(7)]
            bucket = new_bucket()
            model_buckets = {model_name: new_bucket() for model_name in model_order}
            rows = (
                self.db.query(
                    LLMRequestLog.created_at,
                    LLMRequestLog.status,
                    LLMRequestLog.total_tokens,
                    LLMRequestLog.latency_ms,
                    LLMRequestLog.model_name,
                )
                .filter(LLMRequestLog.deleted.is_(False), LLMRequestLog.created_at >= start)
                .all()
            )
            for created_at, status, total_tokens, latency_ms, model_name in rows:
                if not created_at:
                    continue
                label = created_at.strftime("%m-%d")
                if label not in bucket:
                    continue
                touch_bucket(bucket[label], status=str(status or ""), total_tokens=int(total_tokens or 0), latency_ms=latency_ms)
                model_key = str(model_name or "")
                if model_key in model_buckets:
                    touch_bucket(model_buckets[model_key][label], status=str(status or ""), total_tokens=int(total_tokens or 0), latency_ms=latency_ms)
        else:
            start = now - timedelta(hours=23)
            labels = [(start + timedelta(hours=index)).strftime("%H:00") for index in range(24)]
            bucket = new_bucket()
            model_buckets = {model_name: new_bucket() for model_name in model_order}
            rows = (
                self.db.query(
                    LLMRequestLog.created_at,
                    LLMRequestLog.status,
                    LLMRequestLog.total_tokens,
                    LLMRequestLog.latency_ms,
                    LLMRequestLog.model_name,
                )
                .filter(LLMRequestLog.deleted.is_(False), LLMRequestLog.created_at >= start)
                .all()
            )
            for created_at, status, total_tokens, latency_ms, model_name in rows:
                if not created_at:
                    continue
                label = created_at.strftime("%H:00")
                if label not in bucket:
                    continue
                touch_bucket(bucket[label], status=str(status or ""), total_tokens=int(total_tokens or 0), latency_ms=latency_ms)
                model_key = str(model_name or "")
                if model_key in model_buckets:
                    touch_bucket(model_buckets[model_key][label], status=str(status or ""), total_tokens=int(total_tokens or 0), latency_ms=latency_ms)

        model_series = []
        for model_config in monitored_models:
            model_name = str(model_config.get("model_name") or "")
            model_bucket = model_buckets.get(model_name) or {}
            model_series.append(
                {
                    "provider": str(model_config.get("provider") or ""),
                    "model_name": model_name,
                    "label": str(model_config.get("label") or model_name or "model"),
                    "request_counts": [int((model_bucket.get(label) or {}).get("request_count") or 0) for label in labels],
                    "total_tokens": [int((model_bucket.get(label) or {}).get("total_tokens") or 0) for label in labels],
                    "failed_counts": [int((model_bucket.get(label) or {}).get("failed_count") or 0) for label in labels],
                    "avg_latency_ms": [
                        round(
                            float((model_bucket.get(label) or {}).get("latency_sum") or 0)
                            / float((model_bucket.get(label) or {}).get("latency_count") or 1),
                            2,
                        )
                        if float((model_bucket.get(label) or {}).get("latency_count") or 0) > 0
                        else 0
                        for label in labels
                    ],
                }
            )

        return {
            "mode": "7d" if by_day else "24h",
            "labels": labels,
            "request_counts": [bucket[label]["request_count"] for label in labels],
            "total_tokens": [bucket[label]["total_tokens"] for label in labels],
            "failed_counts": [bucket[label]["failed_count"] for label in labels],
            "avg_latency_ms": [
                round(bucket[label]["latency_sum"] / bucket[label]["latency_count"], 2)
                if bucket[label]["latency_count"]
                else 0
                for label in labels
            ],
            "models": model_series,
        }

    def get_llm_logs(self, *, page: int = 1, page_size: int = 20, limit: int | None = None) -> dict[str, Any]:
        page = max(int(page or 1), 1)
        page_size = max(min(int(page_size or 20), 100), 1)
        if limit is not None:
            page_size = max(min(int(limit), 100), 1)
            page = 1

        query = (
            self.db.query(LLMRequestLog)
            .filter(LLMRequestLog.deleted.is_(False))
            .order_by(LLMRequestLog.created_at.desc(), LLMRequestLog.id.desc())
        )
        total = query.count()
        rows = query.offset((page - 1) * page_size).limit(page_size).all()
        items = [
            {
                "created_at": row.created_at.isoformat(timespec="seconds") if row.created_at else "",
                "provider": row.provider,
                "model_name": row.model_name,
                "scene": row.scene,
                "status": row.status,
                "prompt_tokens": int(row.prompt_tokens or 0),
                "completion_tokens": int(row.completion_tokens or 0),
                "total_tokens": int(row.total_tokens or 0),
                "latency_ms": float(row.latency_ms or 0),
                "error_message": row.error_message or "",
                "user_id": row.user_id,
                "session_id": row.session_id,
            }
            for row in rows
        ]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def ping_llm(self) -> dict[str, Any]:
        provider, model_name, api_base_url, has_api_key = self._llm_runtime_config()
        llm_service = get_llm_service()
        llm_service.clear_last_call_meta()
        reply = ""
        status = "degraded"
        error_message = ""

        try:
            reply = llm_service.chat(
                user_role="admin",
                user_name="system",
                message="你好",
                history=[],
                context={"scene": "healthcheck", "reply_mode": "brief", "small_talk": True},
            )
            meta = llm_service.get_last_call_meta() or {}
        except Exception as exc:
            meta = {
                "provider": provider,
                "model_name": model_name,
                "scene": "healthcheck",
                "status": "failed",
                "latency_ms": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "input_chars": 2,
                "output_chars": 0,
                "error_message": str(exc),
                "raw_usage_json": {},
                "raw_meta_json": {"source": "healthcheck_exception"},
            }

        status = "online" if str(meta.get("status") or "failed") == "success" else "degraded"
        if not has_api_key and provider != "mock":
            status = "offline"
            error_message = "未配置 API Key"
        elif status != "online":
            error_message = str(meta.get("error_message") or "模型调用异常")

        self._safe_write_llm_log(meta=meta, scene="healthcheck")

        return {
            "provider": provider,
            "model_name": model_name,
            "api_base_url": api_base_url,
            "connection_status": status,
            "status": str(meta.get("status") or "failed"),
            "latency_ms": float(meta.get("latency_ms") or 0),
            "prompt_tokens": int(meta.get("prompt_tokens") or 0),
            "completion_tokens": int(meta.get("completion_tokens") or 0),
            "total_tokens": int(meta.get("total_tokens") or 0),
            "error_message": error_message or str(meta.get("error_message") or ""),
            "reply_preview": str(reply or "")[:80],
        }

    def _safe_write_llm_log(self, *, meta: dict[str, Any], scene: str) -> None:
        try:
            row = LLMRequestLog(
                provider=str(meta.get("provider") or "mock"),
                model_name=str(meta.get("model_name") or "mock"),
                scene=str(meta.get("scene") or scene),
                user_id=None,
                session_id=None,
                request_id=str(meta.get("request_id") or uuid4()),
                status=str(meta.get("status") or "success"),
                latency_ms=float(meta.get("latency_ms") or 0),
                prompt_tokens=int(meta.get("prompt_tokens") or 0),
                completion_tokens=int(meta.get("completion_tokens") or 0),
                total_tokens=int(meta.get("total_tokens") or 0),
                input_chars=int(meta.get("input_chars") or 0),
                output_chars=int(meta.get("output_chars") or 0),
                error_message=str(meta.get("error_message") or "")[:500] or None,
                raw_usage_json=meta.get("raw_usage_json") or {},
                raw_meta_json=meta.get("raw_meta_json") or {},
            )
            self.db.add(row)
            self.db.commit()
        except Exception:
            self.db.rollback()

    def _llm_runtime_config(self) -> tuple[str, str, str, bool]:
        provider = str(self.settings.LLM_PROVIDER or "mock").lower()
        if provider == "openai":
            model_name = self.settings.OPENAI_MODEL
            api_base_url = self.settings.OPENAI_BASE_URL
            has_api_key = bool(self.settings.OPENAI_API_KEY)
        elif provider == "qwen":
            model_name = self.settings.LANGCHAIN_MODEL
            api_base_url = self.settings.LANGCHAIN_BASE_URL
            has_api_key = bool(self.settings.DASHSCOPE_API_KEY or self.settings.OPENAI_API_KEY)
        else:
            model_name = "mock"
            api_base_url = ""
            has_api_key = True
        return provider, model_name, self._mask_vector_uri(api_base_url) or "", has_api_key

    def _llm_monitored_models(self) -> list[dict[str, Any]]:
        provider, model_name, api_base_url, has_api_key = self._llm_runtime_config()
        models: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, str]] = set()

        def push(*, label: str, model_provider: str, model_name_value: str, model_api_base_url: str, model_has_api_key: bool) -> None:
            normalized_name = str(model_name_value or "").strip()
            normalized_provider = str(model_provider or "").strip().lower() or "unknown"
            if not normalized_name:
                return
            key = (normalized_provider, normalized_name)
            if key in seen_keys:
                return
            seen_keys.add(key)
            models.append(
                {
                    "label": label,
                    "provider": normalized_provider,
                    "model_name": normalized_name,
                    "api_base_url": model_api_base_url,
                    "has_api_key": bool(model_has_api_key),
                }
            )

        push(
            label="主对话模型",
            model_provider=provider,
            model_name_value=model_name,
            model_api_base_url=api_base_url,
            model_has_api_key=has_api_key,
        )

        secondary_provider = self._infer_provider_by_base_url(self.settings.LANGCHAIN_BASE_URL, default_provider=provider)
        secondary_api_base_url = self._mask_vector_uri(self.settings.LANGCHAIN_BASE_URL) or ""
        secondary_has_api_key = bool(self.settings.DASHSCOPE_API_KEY or self.settings.OPENAI_API_KEY)

        vision_model = str(self.settings.RESUME_VISION_MODEL or "").strip()
        if vision_model and vision_model != model_name:
            push(
                label="简历视觉模型",
                model_provider=secondary_provider,
                model_name_value=vision_model,
                model_api_base_url=secondary_api_base_url,
                model_has_api_key=secondary_has_api_key,
            )
        else:
            parser_text_model = str(self.settings.LANGCHAIN_MODEL or "").strip()
            if parser_text_model and parser_text_model != model_name:
                push(
                    label="简历解析模型",
                    model_provider=secondary_provider,
                    model_name_value=parser_text_model,
                    model_api_base_url=secondary_api_base_url,
                    model_has_api_key=secondary_has_api_key,
                )
        return models

    def _build_model_overview(
        self,
        *,
        model_config: dict[str, Any],
        base_query,
        day_start: datetime,
    ) -> dict[str, Any]:
        provider = str(model_config.get("provider") or "unknown")
        model_name = str(model_config.get("model_name") or "unknown")
        api_base_url = str(model_config.get("api_base_url") or "")
        has_api_key = bool(model_config.get("has_api_key"))
        label = str(model_config.get("label") or model_name)

        model_query = base_query.filter(LLMRequestLog.model_name == model_name)
        today_query = model_query.filter(LLMRequestLog.created_at >= day_start)

        today_request_count = int(today_query.count() or 0)
        today_success_count = int(today_query.filter(LLMRequestLog.status == "success").count() or 0)
        today_failed_count = int(today_query.filter(LLMRequestLog.status == "failed").count() or 0)
        today_total_tokens = int(today_query.with_entities(func.coalesce(func.sum(LLMRequestLog.total_tokens), 0)).scalar() or 0)
        avg_latency = today_query.with_entities(func.avg(LLMRequestLog.latency_ms)).scalar()
        avg_latency_ms = round(float(avg_latency), 2) if avg_latency is not None else 0.0

        last_success = (
            model_query.filter(LLMRequestLog.status == "success")
            .order_by(LLMRequestLog.created_at.desc(), LLMRequestLog.id.desc())
            .first()
        )
        last_failed = (
            model_query.filter(LLMRequestLog.status == "failed")
            .order_by(LLMRequestLog.created_at.desc(), LLMRequestLog.id.desc())
            .first()
        )
        connection_status = self._infer_llm_connection_status(
            provider=provider,
            has_api_key=has_api_key,
            today_request_count=today_request_count,
            today_success_count=today_success_count,
            last_success=last_success,
            last_failed=last_failed,
        )
        success_rate = round((today_success_count / today_request_count) * 100, 2) if today_request_count else 0.0

        return {
            "label": label,
            "provider": provider,
            "model_name": model_name,
            "api_base_url": api_base_url,
            "connection_status": connection_status,
            "last_success_at": last_success.created_at.isoformat(timespec="seconds") if last_success and last_success.created_at else "",
            "last_error_at": last_failed.created_at.isoformat(timespec="seconds") if last_failed and last_failed.created_at else "",
            "last_error_message": (last_failed.error_message or "") if last_failed else "",
            "today_request_count": today_request_count,
            "today_success_count": today_success_count,
            "today_failed_count": today_failed_count,
            "today_total_tokens": today_total_tokens,
            "avg_latency_ms": avg_latency_ms,
            "success_rate": success_rate,
        }

    @staticmethod
    def _infer_llm_connection_status(
        *,
        provider: str,
        has_api_key: bool,
        today_request_count: int,
        today_success_count: int,
        last_success,
        last_failed,
    ) -> str:
        if not has_api_key and provider != "mock":
            return "offline"
        if last_success and (not last_failed or last_success.created_at >= last_failed.created_at):
            return "online"
        if today_request_count > 0 and today_success_count > 0:
            return "degraded"
        if today_request_count > 0 and today_success_count == 0:
            return "offline"
        return "degraded"

    @staticmethod
    def _merge_connection_status(statuses: list[str]) -> str:
        normalized = [item for item in (str(status or "").lower() for status in statuses) if item]
        if not normalized:
            return "unknown"
        if all(item == "online" for item in normalized):
            return "online"
        if any(item == "online" for item in normalized):
            return "degraded"
        if any(item == "degraded" for item in normalized):
            return "degraded"
        if all(item == "offline" for item in normalized):
            return "offline"
        return "degraded"

    @staticmethod
    def _infer_provider_by_base_url(base_url: str | None, default_provider: str) -> str:
        text = str(base_url or "").strip().lower()
        if "dashscope" in text:
            return "qwen"
        if "openai.com" in text:
            return "openai"
        return str(default_provider or "unknown").lower()

    def _system_counts(self) -> dict[str, int]:
        return {
            "user_count": self.db.query(func.count(User.id)).filter(User.deleted.is_(False)).scalar() or 0,
            "student_count": self.db.query(func.count(Student.id)).filter(Student.deleted.is_(False)).scalar() or 0,
            "enterprise_count": self.db.query(func.count(EnterpriseProfile.id)).filter(EnterpriseProfile.deleted.is_(False)).scalar() or 0,
            "job_count": self.db.query(func.count(Job.id)).filter(Job.deleted.is_(False)).scalar() or 0,
            "profile_count": self.db.query(func.count(StudentProfile.id)).filter(StudentProfile.deleted.is_(False)).scalar() or 0,
            "match_count": self.db.query(func.count(JobMatchResult.id)).filter(JobMatchResult.deleted.is_(False)).scalar() or 0,
            "report_count": self.db.query(func.count(Report.id)).filter(Report.deleted.is_(False)).scalar() or 0,
            "delivery_count": self.db.query(func.count(ResumeDelivery.id)).filter(ResumeDelivery.deleted.is_(False)).scalar() or 0,
            "attachment_count": self.db.query(func.count(StudentAttachment.id)).filter(StudentAttachment.deleted.is_(False)).scalar() or 0,
            "config_count": self.db.query(func.count(SystemConfig.id)).filter(SystemConfig.deleted.is_(False)).scalar() or 0,
        }

    def _role_distribution(self) -> list[dict[str, Any]]:
        rows = (
            self.db.query(Role.code, Role.name, func.count(User.id))
            .outerjoin(User, (User.role_id == Role.id) & User.deleted.is_(False))
            .filter(Role.deleted.is_(False))
            .group_by(Role.code, Role.name)
            .all()
        )
        return [
            {
                "role_code": code,
                "role_name": name,
                "count": int(count or 0),
            }
            for code, name, count in rows
        ]

    def _business_db_status(self) -> dict[str, Any]:
        inspector = inspect(engine)
        masked_url = self._mask_database_url(str(engine.url))
        status = {
            "status": "unknown",
            "dialect": engine.dialect.name,
            "driver": engine.url.drivername,
            "database": engine.url.database,
            "url": masked_url,
            "table_count": 0,
            "table_names": [],
            "latency_ms": None,
            "server_version": None,
            "size_mb": None,
            "message": "",
        }

        try:
            start = perf_counter()
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                status["latency_ms"] = round((perf_counter() - start) * 1000, 2)
                status["table_names"] = sorted(inspector.get_table_names())
                status["table_count"] = len(status["table_names"])
                status["server_version"] = self._database_version(connection)
                status["size_mb"] = self._database_size_mb(connection, engine.dialect.name)
            status["status"] = "online"
            status["message"] = "业务数据库连接正常"
        except SQLAlchemyError as exc:
            status["status"] = "offline"
            status["message"] = str(exc)
        return status

    def _database_version(self, connection) -> str | None:
        try:
            if engine.dialect.name == "sqlite":
                return str(connection.execute(text("select sqlite_version()")).scalar())
            return str(connection.execute(text("SELECT VERSION()")).scalar())
        except Exception:
            return None

    def _database_size_mb(self, connection, dialect: str) -> float | None:
        try:
            if dialect == "sqlite":
                db_path = Path(engine.url.database or "")
                if db_path.exists():
                    return round(db_path.stat().st_size / 1024 / 1024, 2)
                return 0.0
            if dialect == "mysql":
                size_bytes = connection.execute(
                    text(
                        """
                        SELECT COALESCE(SUM(data_length + index_length), 0)
                        FROM information_schema.tables
                        WHERE table_schema = DATABASE()
                        """
                    )
                ).scalar()
                return round(float(size_bytes or 0) / 1024 / 1024, 2)
        except Exception:
            return None
        return None

    def _vector_db_status(self) -> dict[str, Any]:
        try:
            info = self.vector_service.describe() or {}
            backend = info.get("backend") or "unknown"
            sample_documents = self.vector_service.list_documents(limit=200)
            document_count = self.vector_service.count_documents()
        except Exception as exc:
            return {
                "status": "error",
                "backend": "unknown",
                "mode": "unknown",
                "collection_name": None,
                "uri": None,
                "document_count": 0,
                "company_count": 0,
                "category_count": 0,
                "sample_companies": [],
                "sample_jobs": [],
                "message": f"知识库状态检测异常：{exc}",
            }

        companies = sorted(
            {
                (doc.get("metadata") or {}).get("company_name")
                for doc in sample_documents
                if (doc.get("metadata") or {}).get("company_name")
            }
        )
        categories = sorted({doc.get("job_category") for doc in sample_documents if doc.get("job_category")})
        sample_jobs = [doc.get("job_name") for doc in sample_documents if doc.get("job_name")][:6]

        if backend == "unknown":
            return {
                "status": "error",
                "backend": backend,
                "mode": "unknown",
                "collection_name": info.get("collection_name"),
                "uri": self._mask_vector_uri(info.get("uri")),
                "document_count": int(document_count or 0),
                "company_count": len(companies),
                "category_count": len(categories),
                "sample_companies": companies[:6],
                "sample_jobs": sample_jobs,
                "message": "主知识库状态未知，请检查向量库配置",
            }

        is_fallback = backend == "local-fallback"
        return {
            "status": "degraded" if is_fallback else "online",
            "backend": backend,
            "mode": "fallback" if is_fallback else "primary",
            "collection_name": info.get("collection_name"),
            "uri": self._mask_vector_uri(info.get("uri")),
            "document_count": int(document_count or 0),
            "company_count": len(companies),
            "category_count": len(categories),
            "sample_companies": companies[:6],
            "sample_jobs": sample_jobs,
            "message": "当前运行在本地降级库，数量可能不是主库全量，请检查 Milvus 环境或同步状态" if is_fallback else "主知识库运行正常",
        }

    def _crm_dashboard(self) -> dict[str, Any]:
        users = (
            self.db.query(User)
            .options(joinedload(User.role), joinedload(User.department), joinedload(User.classroom))
            .filter(User.deleted.is_(False))
            .order_by(User.created_at.desc())
            .all()
        )
        enterprises = (
            self.db.query(EnterpriseProfile)
            .options(joinedload(EnterpriseProfile.user), joinedload(EnterpriseProfile.deliveries))
            .filter(EnterpriseProfile.deleted.is_(False))
            .order_by(EnterpriseProfile.created_at.desc())
            .all()
        )

        account_rows = [
            {
                "id": user.id,
                "username": user.username,
                "real_name": user.real_name,
                "role_name": user.role.name if user.role else "未分配角色",
                "role_code": user.role.code if user.role else "",
                "email": user.email or "",
                "phone": user.phone or "",
                "is_active": bool(user.is_active),
                "department": user.department.name if user.department else "",
                "classroom": user.classroom.name if user.classroom else "",
                "created_at": user.created_at.isoformat(timespec="seconds") if user.created_at else "",
            }
            for user in users
        ]

        enterprise_rows: list[dict[str, Any]] = []
        industry_counter: dict[str, int] = {}
        for enterprise in enterprises:
            deliveries = [item for item in enterprise.deliveries if not item.deleted]
            avg_match = round(sum(float(item.match_score or 0) for item in deliveries) / len(deliveries), 1) if deliveries else 0
            pending_reviews = len([item for item in deliveries if not item.enterprise_feedback])
            industry = enterprise.industry or "未分类"
            industry_counter[industry] = industry_counter.get(industry, 0) + 1
            enterprise_rows.append(
                {
                    "id": enterprise.id,
                    "company_name": enterprise.company_name,
                    "industry": industry,
                    "company_type": enterprise.company_type or "",
                    "company_size": enterprise.company_size or "",
                    "address": enterprise.address or "",
                    "account_username": enterprise.user.username if enterprise.user else "",
                    "account_active": bool(enterprise.user.is_active) if enterprise.user else False,
                    "source_doc_count": len(enterprise.source_doc_ids or []),
                    "delivery_count": len(deliveries),
                    "pending_review_count": pending_reviews,
                    "avg_match_score": avg_match,
                    "last_delivery_at": max((item.created_at for item in deliveries), default=None).isoformat(timespec="seconds")
                    if deliveries
                    else "",
                    "created_at": enterprise.created_at.isoformat(timespec="seconds") if enterprise.created_at else "",
                }
            )

        role_distribution = self._role_distribution()
        account_growth = self._build_monthly_trend([item.created_at for item in users if item.created_at])
        enterprise_growth = self._build_monthly_trend([item.created_at for item in enterprises if item.created_at])
        delivery_rank = sorted(
            enterprise_rows,
            key=lambda item: (item["delivery_count"], item["avg_match_score"]),
            reverse=True,
        )[:8]

        active_accounts = len([item for item in users if item.is_active])
        accounts_with_phone = len([item for item in users if item.phone])
        enterprises_with_account = len([item for item in enterprises if item.user])
        enterprises_with_delivery = len([item for item in enterprise_rows if item["delivery_count"] > 0])

        return {
            "metrics": {
                "registered_account_count": len(users),
                "active_account_count": active_accounts,
                "enterprise_total_count": len(enterprises),
                "enterprise_with_account_count": enterprises_with_account,
                "enterprise_with_delivery_count": enterprises_with_delivery,
                "account_completion_rate": round((accounts_with_phone / len(users)) * 100, 1) if users else 0,
            },
            "accounts": account_rows,
            "enterprises": enterprise_rows,
            "charts": {
                "role_distribution": role_distribution,
                "account_growth": account_growth,
                "enterprise_growth": enterprise_growth,
                "enterprise_industry_distribution": [
                    {"name": key, "value": value}
                    for key, value in sorted(industry_counter.items(), key=lambda item: item[1], reverse=True)
                ],
                "enterprise_delivery_rank": [
                    {
                        "name": item["company_name"],
                        "value": item["delivery_count"],
                        "avg_match_score": item["avg_match_score"],
                    }
                    for item in delivery_rank
                ],
            },
            "insights": [
                {
                    "title": "账号活跃度",
                    "value": f"{active_accounts}/{len(users)}",
                    "description": "当前处于启用状态的注册账号数量。",
                },
                {
                    "title": "企业接入率",
                    "value": f"{enterprises_with_account}/{len(enterprises) if enterprises else 0}",
                    "description": "数据库中企业资料与登录账号绑定的覆盖情况。",
                },
                {
                    "title": "企业活跃度",
                    "value": f"{enterprises_with_delivery}/{len(enterprises) if enterprises else 0}",
                    "description": "至少收到过一份学生投递简历的企业数量。",
                },
            ],
        }

    def _highlights(
        self,
        counts: dict[str, int],
        business_db: dict[str, Any],
        vector_db: dict[str, Any],
    ) -> list[dict[str, str]]:
        highlights = [
            {
                "title": "业务库状态",
                "value": "正常" if business_db["status"] == "online" else "异常",
                "description": f"{business_db['dialect']} / {business_db['table_count']} 张表",
            },
            {
                "title": "岗位知识库",
                "value": f"{vector_db['document_count']} 条",
                "description": f"{vector_db['backend']} / {vector_db['company_count']} 家企业来源",
            },
            {
                "title": "投递闭环",
                "value": f"{counts['delivery_count']} 份",
                "description": f"覆盖 {counts['student_count']} 名学生与 {counts['enterprise_count']} 家企业",
            },
            {
                "title": "画像与匹配",
                "value": f"{counts['profile_count']} / {counts['match_count']}",
                "description": "画像数量 / 匹配结果数量",
            },
        ]
        return highlights

    @staticmethod
    def _build_monthly_trend(values: list[Any]) -> list[dict[str, Any]]:
        counter: dict[str, int] = {}
        for value in values:
            if not value:
                continue
            label = value.strftime("%Y-%m")
            counter[label] = counter.get(label, 0) + 1
        return [{"label": label, "value": count} for label, count in sorted(counter.items())]

    @staticmethod
    def _mask_database_url(raw_url: str) -> str:
        parsed = urlsplit(raw_url)
        if not parsed.netloc:
            return raw_url
        username = parsed.username or ""
        hostname = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        auth = f"{username}:***@" if username else ""
        return urlunsplit((parsed.scheme, f"{auth}{hostname}{port}", parsed.path, parsed.query, parsed.fragment))

    @staticmethod
    def _mask_vector_uri(uri: str | None) -> str | None:
        if not uri:
            return uri
        if "://" in uri:
            return SystemMonitorService._mask_database_url(uri)
        path = Path(uri)
        if path.is_absolute():
            return str(path)
        return uri
