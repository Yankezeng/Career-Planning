from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.agent.common.model_manager import (
    ModelDownloadError,
    ModelNotAvailableError,
    ensure_model_available,
    is_model_ready,
    log_model_config,
)


def _download_one(name: str, repo_id: str, local_dir: str) -> bool:
    print(f"\n{'='*60}")
    print(f"  模型: {name}")
    print(f"  Repo: {repo_id}")
    print(f"  本地目录: {local_dir}")
    print(f"{'='*60}")

    if is_model_ready(local_dir):
        print(f"[OK] 本地模型已存在，跳过下载: {local_dir}")
        return True

    print("[...] 开始下载...")
    t0 = time.time()
    try:
        result = ensure_model_available(
            repo_id=repo_id,
            local_dir=local_dir,
            local_files_only=False,
            offline=False,
        )
        elapsed = time.time() - t0
        print(f"[OK] 下载完成 ({elapsed:.1f}s) -> {result}")
        return True
    except ModelNotAvailableError as e:
        print(f"[FAIL] 模型不可用: {e}")
        return False
    except ModelDownloadError as e:
        print(f"[FAIL] 下载失败: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] 异常: {type(e).__name__}: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="预下载 HuggingFace 模型到本地目录（用于离线运行或加速启动）",
    )
    parser.add_argument(
        "--embedding-only", action="store_true", help="仅下载 embedding 模型"
    )
    parser.add_argument(
        "--reranker-only", action="store_true", help="仅下载 reranker 模型"
    )
    parser.add_argument(
        "--embedding-repo", default=None, help="覆盖 embedding 模型 repo id"
    )
    parser.add_argument(
        "--reranker-repo", default=None, help="覆盖 reranker 模型 repo id"
    )
    parser.add_argument(
        "--embedding-dir", default=None, help="覆盖 embedding 模型本地目录"
    )
    parser.add_argument(
        "--reranker-dir", default=None, help="覆盖 reranker 模型本地目录"
    )
    args = parser.parse_args()

    import os

    log_model_config()

    embedding_repo = args.embedding_repo or os.environ.get(
        "EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    reranker_repo = args.reranker_repo or os.environ.get(
        "RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
    )
    embedding_dir = args.embedding_dir or os.environ.get("EMBEDDING_MODEL_DIR", "./models/embedding")
    reranker_dir = args.reranker_dir or os.environ.get("RERANKER_MODEL_DIR", "./models/reranker")

    results: list[tuple[str, bool]] = []

    if not args.reranker_only:
        ok = _download_one("Embedding", embedding_repo, embedding_dir)
        results.append(("Embedding", ok))

    if not args.embedding_only:
        ok = _download_one("Reranker", reranker_repo, reranker_dir)
        results.append(("Reranker", ok))

    print(f"\n{'='*60}")
    print("  下载结果汇总")
    print(f"{'='*60}")
    all_ok = True
    for name, ok in results:
        status = "[OK]" if ok else "[FAIL]"
        print(f"  {status} {name}")
        if not ok:
            all_ok = False

    if all_ok:
        print("\n所有模型已就绪！项目现在可以离线运行。")
        print(f"提示：将 models/ 目录随项目一起打包即可在无网络环境使用。")
        sys.exit(0)
    else:
        print("\n部分模型下载失败，请检查网络或配置后重试。")
        sys.exit(1)


if __name__ == "__main__":
    main()
