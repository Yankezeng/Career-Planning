from __future__ import annotations

import logging
import os
import inspect
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REQUIRED_CONFIG_FILES = {"config.json", "pytorch_model.bin", "model.safetensors", "tokenizer_config.json"}
_DOWNLOAD_TIMEOUT_ENV = "MODEL_DOWNLOAD_TIMEOUT"


def _get_base_dir() -> Path:
    try:
        from app.core.project_paths import PROJECT_ROOT
        return PROJECT_ROOT
    except ImportError:
        return Path.cwd()


def _resolve_model_dir(relative_dir: str) -> Path:
    base = _get_base_dir()
    return (base / relative_dir).resolve()


def _get_download_timeout() -> int:
    try:
        return int(os.environ.get(_DOWNLOAD_TIMEOUT_ENV, "120"))
    except (ValueError, TypeError):
        return 120


def is_model_ready(local_dir: str | Path) -> bool:
    dir_path = Path(local_dir)
    if not dir_path.is_dir():
        return False
    existing = {f.name for f in dir_path.iterdir() if f.is_file() and f.stat().st_size > 0}
    has_config = "config.json" in existing or "tokenizer_config.json" in existing
    has_weights = "model.safetensors" in existing or "pytorch_model.bin" in existing or "model.onnx" in existing
    return has_config and has_weights


def _resolve_token(token: str | None) -> str | None:
    if token:
        return token
    env_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN") or ""
    return env_token or None


def _build_snapshot_download_kwargs(
    snapshot_download_fn: Any,
    *,
    repo_id: str,
    local_dir: str | Path,
    token: str | None,
    timeout: int,
) -> dict[str, Any]:
    params = inspect.signature(snapshot_download_fn).parameters
    kwargs: dict[str, Any] = {"repo_id": repo_id}

    if "local_dir" in params:
        kwargs["local_dir"] = str(local_dir)

    if token is not None:
        if "token" in params:
            kwargs["token"] = token
        elif "use_auth_token" in params:
            kwargs["use_auth_token"] = token

    if "local_dir_use_symlinks" in params:
        kwargs["local_dir_use_symlinks"] = False

    if "timeout" in params:
        kwargs["timeout"] = timeout
    elif "etag_timeout" in params:
        kwargs["etag_timeout"] = timeout

    if "resume_download" in params:
        kwargs["resume_download"] = True

    return kwargs


def ensure_model_available(
    repo_id: str,
    local_dir: str | Path,
    token: str | None = None,
    local_files_only: bool = False,
    offline: bool = False,
) -> Path:
    local_dir = _resolve_model_dir(str(local_dir))
    token = _resolve_token(token)

    if offline or local_files_only:
        if is_model_ready(local_dir):
            logger.info("[ModelManager] 离线/本地模式，使用本地模型目录: %s", local_dir)
            return local_dir
        logger.warning("[ModelManager] 离线模式但本地模型不存在: %s", local_dir)
        raise ModelNotAvailableError(
            f"本地模型目录不存在或不完整: {local_dir} (offline={offline}, local_files_only={local_files_only})"
        )

    auto_download = os.environ.get("HF_MODEL_AUTO_DOWNLOAD", "true").lower() in ("1", "true", "yes")
    if is_model_ready(local_dir):
        logger.info("[ModelManager] 本地模型已就绪，跳过下载: %s", local_dir)
        return local_dir

    if not auto_download:
        logger.warning("[ModelManager] 自动下载已禁用 (HF_MODEL_AUTO_DOWNLOAD=false)，且本地模型不存在: %s", local_dir)
        raise ModelNotAvailableError(f"自动下载已禁用且本地模型不存在: {local_dir}")

    logger.info("[ModelManager] 本地模型不存在，开始从 HuggingFace 下载: %s -> %s", repo_id, local_dir)
    local_dir.mkdir(parents=True, exist_ok=True)

    try:
        from huggingface_hub import snapshot_download

        timeout = _get_download_timeout()
        start = time.time()
        download_kwargs = _build_snapshot_download_kwargs(
            snapshot_download,
            repo_id=repo_id,
            local_dir=local_dir,
            token=token,
            timeout=timeout,
        )
        downloaded = snapshot_download(**download_kwargs)

        elapsed = time.time() - start
        logger.info("[ModelManager] 下载完成，耗时 %.1fs，路径: %s", elapsed, downloaded)
        return Path(downloaded)
    except ImportError:
        logger.error("[ModelManager] huggingface_hub 未安装，无法下载模型")
        raise ModelNotAvailableError("huggingface_hub 未安装，请执行: pip install huggingface_hub")
    except Exception as exc:
        logger.error("[ModelManager] 模型下载失败 [%s]: %s", repo_id, exc, exc_info=True)
        raise ModelDownloadError(f"从 HuggingFace 下载模型失败 ({repo_id}): {exc}") from exc


def load_sentence_transformer(
    model_name_or_path: str | Path,
    *,
    token: str | None = None,
    local_files_only_override: bool | None = None,
) -> Any:
    from sentence_transformers import SentenceTransformer

    path = str(model_name_or_path)
    token = _resolve_token(token)
    lfo = (
        local_files_only_override
        if local_files_only_override is not None
        else os.environ.get("HF_MODEL_LOCAL_FILES_ONLY", "false").lower() in ("1", "true", "yes")
    )
    kwargs: dict[str, Any] = {"local_files_only": lfo}
    if token:
        kwargs["token"] = token

    logger.info("[ModelManager] 加载 SentenceTransformer: %s (local_files_only=%s)", path, lfo)
    return SentenceTransformer(path, **kwargs)


def load_cross_encoder(
    model_name_or_path: str | Path,
    *,
    token: str | None = None,
    local_files_only_override: bool | None = None,
) -> Any:
    from sentence_transformers import CrossEncoder

    path = str(model_name_or_path)
    token = _resolve_token(token)
    lfo = (
        local_files_only_override
        if local_files_only_override is not None
        else os.environ.get("HF_MODEL_LOCAL_FILES_ONLY", "false").lower() in ("1", "true", "yes")
    )
    kwargs: dict[str, Any] = {"local_files_only": lfo}
    if token:
        kwargs["token"] = token

    logger.info("[ModelManager] 加载 CrossEncoder: %s (local_files_only=%s)", path, lfo)
    return CrossEncoder(path, **kwargs)


class ModelNotAvailableError(Exception):
    pass


class ModelDownloadError(Exception):
    pass


_config_logged = False


def log_model_config() -> None:
    global _config_logged
    if _config_logged:
        return
    _config_logged = True
    logger.info(
        "[ModelConfig] ENABLE_INTENT_EMBEDDING=%s | ENABLE_RAG_RERANKER=%s | "
        "HF_MODEL_AUTO_DOWNLOAD=%s | HF_MODEL_LOCAL_FILES_ONLY=%s | HF_HUB_OFFLINE=%s",
        os.environ.get("ENABLE_INTENT_EMBEDDING", "true"),
        os.environ.get("ENABLE_RAG_RERANKER", "true"),
        os.environ.get("HF_MODEL_AUTO_DOWNLOAD", "true"),
        os.environ.get("HF_MODEL_LOCAL_FILES_ONLY", "false"),
        os.environ.get("HF_HUB_OFFLINE", "false"),
    )
