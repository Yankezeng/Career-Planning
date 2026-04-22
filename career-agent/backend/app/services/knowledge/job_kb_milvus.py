from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from app.core.project_paths import PROJECT_ROOT

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None

try:
    from pymilvus import DataType, MilvusClient
except Exception:  # pragma: no cover
    DataType = None
    MilvusClient = None


COLUMN_ALIASES = {
    "job_name": ["岗位名称", "职位名称", "岗位", "职位", "名称", "job_name", "position_name", "title"],
    "job_category": ["岗位类别", "职位类别", "类别", "分类", "job_category", "category"],
    "industry": ["所属行业", "行业", "industry"],
    "description": ["岗位描述", "职位描述", "岗位详情", "职位详情", "岗位说明", "职位说明", "jd", "description"],
    "core_skills": ["核心技能标签", "核心技能", "技能标签", "技能要求", "专业技能", "skill_tags", "skills"],
    "common_skills": ["通用能力标签", "软技能", "通用能力", "能力要求", "soft_skills", "competency"],
    "certificates": ["证书要求", "证书", "资格证书", "certificates"],
    "degree_requirement": ["学历要求", "学历", "degree_requirement", "education_requirement"],
    "major_requirement": ["专业要求", "专业", "major_requirement"],
    "internship_requirement": ["实习要求", "经验要求", "实习经验", "经验", "internship_requirement"],
    "work_content": ["工作内容", "工作职责", "主要职责", "工作任务", "work_content"],
    "development_direction": ["发展方向", "晋升方向", "成长方向", "career_path", "development_direction"],
    "salary_range": ["薪资范围", "薪资", "薪酬范围", "salary_range"],
    "address": ["地址", "工作地点", "城市", "location", "address"],
    "company_name": ["公司名称", "企业名称", "company_name", "company"],
    "company_size": ["公司规模", "规模", "company_size"],
    "company_type": ["公司类型", "融资阶段", "company_type"],
    "job_code": ["岗位编码", "职位编码", "job_code", "position_code"],
    "update_date": ["更新日期", "发布日期", "更新时间", "update_date"],
    "company_detail": ["公司详情", "企业详情", "公司介绍", "company_detail"],
    "source_url": ["岗位来源地址", "职位链接", "source_url", "url", "job_url"],
}


def _normalize_column_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"[\s_\r\n]+", "", text)


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def _split_tags(value: str) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[、,，;/；|/\n]+", value)
    return [item.strip() for item in parts if item.strip()]


def _clean_html_text(value: str) -> str:
    if not value:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    left_vec = np.array(left, dtype=np.float32)
    right_vec = np.array(right, dtype=np.float32)
    left_norm = np.linalg.norm(left_vec)
    right_norm = np.linalg.norm(right_vec)
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return float(np.dot(left_vec, right_vec) / (left_norm * right_norm))


@dataclass
class JobKnowledgeDocument:
    doc_id: str
    job_name: str
    job_category: str
    industry: str
    content: str
    row_index: int
    sheet_name: str
    source_file: str
    metadata: dict[str, Any]

    def to_storage_dict(self, vector: list[float]) -> dict[str, Any]:
        return {
            "id": self.doc_id,
            "job_name": self.job_name,
            "job_category": self.job_category,
            "industry": self.industry,
            "content": self.content,
            "row_index": self.row_index,
            "sheet_name": self.sheet_name,
            "source_file": self.source_file,
            "metadata_json": json.dumps(self.metadata, ensure_ascii=False),
            "vector": vector,
        }


class ExcelJobDataLoader:
    def load(self, file_path: str | os.PathLike[str], sheet_name: str | None = None) -> list[JobKnowledgeDocument]:
        if pd is None:
            raise RuntimeError("缺少 pandas 依赖，请先安装 pandas。")

        target = Path(file_path)
        if not target.exists():
            raise FileNotFoundError(f"Excel 文件不存在: {target}")

        frames = self._read_frames(target, sheet_name)
        if not isinstance(frames, dict):
            frames = {sheet_name or "Sheet1": frames}

        documents: list[JobKnowledgeDocument] = []
        for current_sheet, frame in frames.items():
            documents.extend(self._frame_to_documents(frame, target, str(current_sheet)))
        return documents

    def _read_frames(self, file_path: Path, sheet_name: str | None) -> dict[str, Any]:
        if file_path.suffix.lower() == ".xls":
            try:
                return pd.read_excel(file_path, sheet_name=sheet_name if sheet_name is not None else None)
            except Exception as exc:  # pragma: no cover
                if "xlrd" not in str(exc).lower():
                    raise
                converted = self._convert_xls_to_xlsx(file_path)
                return pd.read_excel(converted, sheet_name=sheet_name if sheet_name is not None else None)

        return pd.read_excel(file_path, sheet_name=sheet_name if sheet_name is not None else None)

    def _convert_xls_to_xlsx(self, file_path: Path) -> Path:
        try:
            import win32com.client
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("读取 .xls 需要 xlrd，或在 Windows 下安装 pywin32 用于自动转换。") from exc

        temp_dir = Path(tempfile.mkdtemp(prefix="career-agent-xls-"))
        output_path = temp_dir / f"{file_path.stem}.xlsx"

        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        workbook = excel.Workbooks.Open(str(file_path.resolve()))
        try:
            workbook.SaveAs(str(output_path), FileFormat=51)
        finally:
            workbook.Close(False)
            excel.Quit()

        return output_path

    def _frame_to_documents(self, frame: Any, source_file: Path, sheet_name: str) -> list[JobKnowledgeDocument]:
        if frame is None or frame.empty:
            return []

        normalized_columns = {column: _normalize_column_name(column) for column in frame.columns}
        mapped_columns = self._map_columns(normalized_columns)
        documents: list[JobKnowledgeDocument] = []

        for position, (_, row) in enumerate(frame.iterrows(), start=2):
            payload = self._extract_row_payload(row, mapped_columns)
            if not payload["job_name"] and not payload["description"]:
                continue

            if not payload["job_category"]:
                payload["job_category"] = self._infer_job_category(payload["job_name"])

            content = self._compose_content(payload)
            if not content:
                continue

            doc_seed = f"{source_file.resolve()}|{sheet_name}|{position}|{payload['job_name']}"
            doc_id = hashlib.sha1(doc_seed.encode("utf-8")).hexdigest()[:32]
            metadata = {key: value for key, value in payload.items() if value}
            documents.append(
                JobKnowledgeDocument(
                    doc_id=doc_id,
                    job_name=payload["job_name"] or f"未命名岗位 {position}",
                    job_category=payload["job_category"],
                    industry=payload["industry"],
                    content=content,
                    row_index=position,
                    sheet_name=sheet_name,
                    source_file=str(source_file),
                    metadata=metadata,
                )
            )

        return documents

    def _map_columns(self, normalized_columns: dict[Any, str]) -> dict[str, Any]:
        reverse_lookup = {normalized: raw for raw, normalized in normalized_columns.items()}
        mapped: dict[str, Any] = {}
        for target, aliases in COLUMN_ALIASES.items():
            for alias in aliases:
                key = _normalize_column_name(alias)
                if key in reverse_lookup:
                    mapped[target] = reverse_lookup[key]
                    break
        return mapped

    def _extract_row_payload(self, row: Any, mapped_columns: dict[str, Any]) -> dict[str, str]:
        payload: dict[str, str] = {}
        for field_name in COLUMN_ALIASES:
            column_name = mapped_columns.get(field_name)
            value = _safe_text(row.get(column_name)) if column_name is not None else ""
            payload[field_name] = _clean_html_text(value)

        if not payload["job_name"]:
            first_non_empty = next((_safe_text(value) for value in row.tolist() if _safe_text(value)), "")
            payload["job_name"] = first_non_empty[:120]

        return payload

    def _compose_content(self, payload: dict[str, str]) -> str:
        sections = [
            f"岗位名称：{payload['job_name']}",
            f"岗位类别：{payload['job_category']}" if payload["job_category"] else "",
            f"工作地点：{payload['address']}" if payload["address"] else "",
            f"薪资范围：{payload['salary_range']}" if payload["salary_range"] else "",
            f"公司名称：{payload['company_name']}" if payload["company_name"] else "",
            f"所属行业：{payload['industry']}" if payload["industry"] else "",
            f"公司规模：{payload['company_size']}" if payload["company_size"] else "",
            f"公司类型：{payload['company_type']}" if payload["company_type"] else "",
            f"岗位编码：{payload['job_code']}" if payload["job_code"] else "",
            f"岗位描述：{payload['description']}" if payload["description"] else "",
            f"核心技能：{'、'.join(_split_tags(payload['core_skills']))}" if payload["core_skills"] else "",
            f"通用能力：{'、'.join(_split_tags(payload['common_skills']))}" if payload["common_skills"] else "",
            f"证书要求：{'、'.join(_split_tags(payload['certificates']))}" if payload["certificates"] else "",
            f"学历要求：{payload['degree_requirement']}" if payload["degree_requirement"] else "",
            f"专业要求：{payload['major_requirement']}" if payload["major_requirement"] else "",
            f"实习要求：{payload['internship_requirement']}" if payload["internship_requirement"] else "",
            f"工作内容：{payload['work_content']}" if payload["work_content"] else "",
            f"发展方向：{payload['development_direction']}" if payload["development_direction"] else "",
            f"更新日期：{payload['update_date']}" if payload["update_date"] else "",
            f"公司详情：{payload['company_detail']}" if payload["company_detail"] else "",
            f"来源地址：{payload['source_url']}" if payload["source_url"] else "",
        ]
        return "\n".join([item for item in sections if item])

    @staticmethod
    def _infer_job_category(job_name: str) -> str:
        normalized = (job_name or "").lower()
        mapping = {
            "开发": "开发",
            "前端": "开发",
            "后端": "开发",
            "java": "开发",
            "python": "开发",
            "产品": "产品",
            "数据": "数据",
            "运营": "运营",
            "设计": "设计",
            "测试": "测试",
            "运维": "运维",
            "销售": "营销",
            "市场": "营销",
            "人力": "职能",
            "hr": "职能",
        }
        for keyword, category in mapping.items():
            if keyword in normalized:
                return category
        return "综合"


class DeterministicHashEmbeddingService:
    def __init__(self, dimension: int = 256):
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        tokens = self._tokenize(text)
        vector = np.zeros(self.dimension, dtype=np.float32)
        if not tokens:
            return vector.tolist()

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + (digest[5] / 255.0) * 0.35
            vector[index] += sign * weight

        norm = float(np.linalg.norm(vector))
        if norm > 0:
            vector /= norm
        return vector.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        if not text:
            return []
        normalized = text.lower()
        return re.findall(r"[a-z0-9_+#./-]+|[\u4e00-\u9fff]{1,4}", normalized)


class LocalVectorStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def ensure_collection(self, drop_old: bool = False) -> None:
        with self._connect() as conn:
            if drop_old:
                conn.execute("DROP TABLE IF EXISTS job_knowledge")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_knowledge (
                    id TEXT PRIMARY KEY,
                    job_name TEXT,
                    job_category TEXT,
                    industry TEXT,
                    content TEXT,
                    row_index INTEGER,
                    sheet_name TEXT,
                    source_file TEXT,
                    metadata_json TEXT,
                    vector_json TEXT
                )
                """
            )
            conn.commit()

    def upsert(self, payloads: list[dict[str, Any]]) -> None:
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO job_knowledge (
                    id, job_name, job_category, industry, content, row_index,
                    sheet_name, source_file, metadata_json, vector_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    job_name=excluded.job_name,
                    job_category=excluded.job_category,
                    industry=excluded.industry,
                    content=excluded.content,
                    row_index=excluded.row_index,
                    sheet_name=excluded.sheet_name,
                    source_file=excluded.source_file,
                    metadata_json=excluded.metadata_json,
                    vector_json=excluded.vector_json
                """,
                [
                    (
                        payload["id"],
                        payload["job_name"],
                        payload["job_category"],
                        payload["industry"],
                        payload["content"],
                        payload["row_index"],
                        payload["sheet_name"],
                        payload["source_file"],
                        payload["metadata_json"],
                        json.dumps(payload["vector"], ensure_ascii=False),
                    )
                    for payload in payloads
                ],
            )
            conn.commit()

    def search(self, query_vector: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        if not self.db_path.exists():
            return []

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, job_name, job_category, industry, content, row_index,
                       sheet_name, source_file, metadata_json, vector_json
                FROM job_knowledge
                """
            ).fetchall()

        scored_rows: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            vector = json.loads(row["vector_json"] or "[]")
            score = _cosine_similarity(query_vector, vector)
            scored_rows.append((score, row))

        scored_rows.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "id": row["id"],
                "score": score,
                "job_name": row["job_name"],
                "job_category": row["job_category"],
                "industry": row["industry"],
                "content": row["content"],
                "row_index": row["row_index"],
                "sheet_name": row["sheet_name"],
                "source_file": row["source_file"],
                "metadata": json.loads(row["metadata_json"] or "{}"),
            }
            for score, row in scored_rows[:top_k]
        ]

    def list_documents(self, limit: int = 5000) -> list[dict[str, Any]]:
        if not self.db_path.exists():
            return []

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, job_name, job_category, industry, content, row_index,
                       sheet_name, source_file, metadata_json, vector_json
                FROM job_knowledge
                ORDER BY source_file ASC, row_index ASC, job_name ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        documents: list[dict[str, Any]] = []
        for row in rows:
            try:
                metadata = json.loads(row["metadata_json"] or "{}")
            except json.JSONDecodeError:
                metadata = {}
            documents.append(
                {
                    "id": row["id"],
                    "job_name": row["job_name"],
                    "job_category": row["job_category"],
                    "industry": row["industry"],
                    "content": row["content"],
                    "row_index": row["row_index"],
                    "sheet_name": row["sheet_name"],
                    "source_file": row["source_file"],
                    "metadata": metadata,
                }
            )
        return documents

    def count(self) -> int:
        if not self.db_path.exists():
            return 0
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS total FROM job_knowledge").fetchone()
        return int(row["total"] or 0)

    def get_document_by_id(self, doc_id: str) -> dict[str, Any] | None:
        if not self.db_path.exists() or not doc_id:
            return None
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, job_name, job_category, industry, content, row_index,
                       sheet_name, source_file, metadata_json
                FROM job_knowledge
                WHERE id = ?
                LIMIT 1
                """,
                (str(doc_id),),
            ).fetchone()
        if not row:
            return None
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except json.JSONDecodeError:
            metadata = {}
        return {
            "id": row["id"],
            "job_name": row["job_name"],
            "job_category": row["job_category"],
            "industry": row["industry"],
            "content": row["content"],
            "row_index": row["row_index"],
            "sheet_name": row["sheet_name"],
            "source_file": row["source_file"],
            "metadata": metadata,
        }

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


class MilvusJobKnowledgeBase:
    def __init__(
        self,
        uri: str | None = None,
        token: str | None = None,
        collection_name: str | None = None,
        embedding_service: DeterministicHashEmbeddingService | None = None,
    ):
        base_dir = PROJECT_ROOT / "backend" / "uploads" / "milvus"
        base_dir.mkdir(parents=True, exist_ok=True)
        self.uri = uri or os.getenv("MILVUS_URI") or str(base_dir / "job_knowledge_base.db")
        self.token = token or os.getenv("MILVUS_TOKEN")
        self.collection_name = collection_name or os.getenv("MILVUS_JOB_COLLECTION", "job_knowledge_base")
        self.embedding_service = embedding_service or DeterministicHashEmbeddingService()
        self.dimension = self.embedding_service.dimension
        self.backend_name = self._resolve_backend_name()
        self.local_store = LocalVectorStore(self._resolve_local_store_path())

    def ensure_collection(self, drop_old: bool = False) -> None:
        if self.backend_name != "milvus":
            self.local_store.ensure_collection(drop_old=drop_old)
            return

        client = self._client()
        if client.has_collection(self.collection_name):
            if drop_old:
                client.drop_collection(self.collection_name)
            else:
                return

        schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field(field_name="id", datatype=DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field(field_name="job_name", datatype=DataType.VARCHAR, max_length=256)
        schema.add_field(field_name="job_category", datatype=DataType.VARCHAR, max_length=128)
        schema.add_field(field_name="industry", datatype=DataType.VARCHAR, max_length=128)
        schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=8192)
        schema.add_field(field_name="row_index", datatype=DataType.INT64)
        schema.add_field(field_name="sheet_name", datatype=DataType.VARCHAR, max_length=128)
        schema.add_field(field_name="source_file", datatype=DataType.VARCHAR, max_length=1024)
        schema.add_field(field_name="metadata_json", datatype=DataType.VARCHAR, max_length=8192)
        schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=self.dimension)

        index_params = client.prepare_index_params()
        index_params.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")
        client.create_collection(collection_name=self.collection_name, schema=schema, index_params=index_params)
        client.load_collection(self.collection_name)

    def import_excel(self, file_path: str, sheet_name: str | None = None, drop_old: bool = False) -> dict[str, Any]:
        loader = ExcelJobDataLoader()
        documents = loader.load(file_path, sheet_name=sheet_name)
        if not documents:
            return {
                "inserted": 0,
                "collection_name": self.collection_name,
                "backend": self.backend_name,
                "sample_jobs": [],
            }

        self.ensure_collection(drop_old=drop_old)
        vectors = self.embedding_service.embed_batch([document.content for document in documents])
        payloads = [document.to_storage_dict(vector) for document, vector in zip(documents, vectors, strict=True)]

        if self.backend_name == "milvus":
            client = self._client()
            client.upsert(collection_name=self.collection_name, data=payloads)
            client.load_collection(self.collection_name)
            total = len(payloads)
        else:
            self.local_store.upsert(payloads)
            total = self.local_store.count()

        return {
            "inserted": len(payloads),
            "stored_total": total,
            "collection_name": self.collection_name,
            "backend": self.backend_name,
            "sample_jobs": [item.job_name for item in documents[:5]],
        }

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if not query.strip():
            return []

        vector = self.embedding_service.embed(query)
        if self.backend_name == "milvus":
            client = self._client()
            if not client.has_collection(self.collection_name):
                return []
            client.load_collection(self.collection_name)
            output_fields = [
                "job_name",
                "job_category",
                "industry",
                "content",
                "row_index",
                "sheet_name",
                "source_file",
                "metadata_json",
            ]
            results = client.search(
                collection_name=self.collection_name,
                data=[vector],
                limit=top_k,
                output_fields=output_fields,
                search_params={"metric_type": "COSINE"},
            )
            return [self._normalize_milvus_hit(hit) for hit in (results[0] if results else [])]

        return self.local_store.search(vector, top_k=top_k)

    def describe(self) -> dict[str, Any]:
        return {
            "backend": self.backend_name,
            "collection_name": self.collection_name,
            "uri": self.uri,
        }

    def list_documents(self, limit: int = 5000) -> list[dict[str, Any]]:
        output_fields = [
            "job_name",
            "job_category",
            "industry",
            "content",
            "row_index",
            "sheet_name",
            "source_file",
            "metadata_json",
        ]
        if self.backend_name != "milvus":
            return self.local_store.list_documents(limit=limit)

        client = self._client()
        if not client.has_collection(self.collection_name):
            return []
        client.load_collection(self.collection_name)
        try:
            results = client.query(
                collection_name=self.collection_name,
                filter='id != ""',
                output_fields=output_fields,
                limit=limit,
            )
        except TypeError:
            results = client.query(
                collection_name=self.collection_name,
                filter='id != ""',
                output_fields=output_fields,
            )[:limit]

        documents: list[dict[str, Any]] = []
        for item in results or []:
            metadata_json = item.get("metadata_json") or "{}"
            try:
                metadata = json.loads(metadata_json)
            except json.JSONDecodeError:
                metadata = {}
            documents.append(
                {
                    "id": item.get("id"),
                    "job_name": item.get("job_name", ""),
                    "job_category": item.get("job_category", ""),
                    "industry": item.get("industry", ""),
                    "content": item.get("content", ""),
                    "row_index": item.get("row_index"),
                    "sheet_name": item.get("sheet_name", ""),
                    "source_file": item.get("source_file", ""),
                    "metadata": metadata,
                }
            )
        documents.sort(
            key=lambda entry: (
                str(entry.get("source_file") or ""),
                int(entry.get("row_index") or 0),
                str(entry.get("job_name") or ""),
            )
        )
        return documents[:limit]

    def count_documents(self) -> int:
        if self.backend_name != "milvus":
            return self.local_store.count()

        client = self._client()
        if not client.has_collection(self.collection_name):
            return 0
        client.load_collection(self.collection_name)
        try:
            stats = client.get_collection_stats(collection_name=self.collection_name) or {}
            for key in ("row_count", "num_entities", "total_rows"):
                if key in stats:
                    return int(stats.get(key) or 0)
        except Exception:
            pass
        try:
            details = client.describe_collection(collection_name=self.collection_name) or {}
            return int(details.get("num_entities") or 0)
        except Exception:
            return 0

    def get_document_by_id(self, doc_id: str) -> dict[str, Any] | None:
        if not doc_id:
            return None

        output_fields = [
            "job_name",
            "job_category",
            "industry",
            "content",
            "row_index",
            "sheet_name",
            "source_file",
            "metadata_json",
        ]
        if self.backend_name != "milvus":
            return self.local_store.get_document_by_id(doc_id)

        client = self._client()
        if not client.has_collection(self.collection_name):
            return None
        client.load_collection(self.collection_name)
        try:
            results = client.query(
                collection_name=self.collection_name,
                filter=f'id == "{str(doc_id)}"',
                output_fields=output_fields,
                limit=1,
            )
        except TypeError:
            results = client.query(
                collection_name=self.collection_name,
                filter=f'id == "{str(doc_id)}"',
                output_fields=output_fields,
            )
        if not results:
            return None

        item = results[0]
        metadata_json = item.get("metadata_json") or "{}"
        try:
            metadata = json.loads(metadata_json)
        except json.JSONDecodeError:
            metadata = {}
        return {
            "id": item.get("id"),
            "job_name": item.get("job_name", ""),
            "job_category": item.get("job_category", ""),
            "industry": item.get("industry", ""),
            "content": item.get("content", ""),
            "row_index": item.get("row_index"),
            "sheet_name": item.get("sheet_name", ""),
            "source_file": item.get("source_file", ""),
            "metadata": metadata,
        }

    def _resolve_backend_name(self) -> str:
        preferred = os.getenv("VECTOR_STORE_BACKEND", "auto").lower()
        if preferred == "local":
            return "local-fallback"
        if preferred == "milvus":
            return "milvus"

        if MilvusClient is None or DataType is None:
            return "local-fallback"

        if self._looks_like_local_file_uri(self.uri):
            try:
                import milvus_lite  # noqa: F401
            except ImportError:
                return "local-fallback"

        return "milvus"

    def _resolve_local_store_path(self) -> Path:
        raw = self.uri or self.collection_name
        if self._looks_like_local_file_uri(raw):
            path = Path(raw)
            if not path.is_absolute():
                path = (PROJECT_ROOT / "backend" / path).resolve()
        else:
            safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", self.collection_name)
            path = (PROJECT_ROOT / "backend" / "uploads" / "milvus" / f"{safe_name}.sqlite3").resolve()
        if any(ord(char) > 127 for char in str(path)):
            safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", Path(path).stem or self.collection_name)
            fallback_dir = Path(tempfile.gettempdir()) / "career-agent-vector-store"
            fallback_dir.mkdir(parents=True, exist_ok=True)
            path = (fallback_dir / f"{safe_name}.sqlite3").resolve()
        return path

    @staticmethod
    def _looks_like_local_file_uri(uri: str) -> bool:
        lowered = str(uri or "").lower()
        return not lowered.startswith(("http://", "https://", "tcp://", "grpc://"))

    def _client(self):
        if MilvusClient is None or DataType is None:
            raise RuntimeError("缺少 pymilvus 依赖，请先安装 pymilvus。")
        kwargs = {"uri": self.uri}
        if self.token:
            kwargs["token"] = self.token
        return MilvusClient(**kwargs)

    @staticmethod
    def _normalize_milvus_hit(hit: dict[str, Any]) -> dict[str, Any]:
        entity = hit.get("entity") or {}
        metadata_json = entity.get("metadata_json") or hit.get("metadata_json") or "{}"
        try:
            metadata = json.loads(metadata_json)
        except json.JSONDecodeError:
            metadata = {}
        return {
            "id": hit.get("id"),
            "score": hit.get("distance", hit.get("score", 0)),
            "job_name": entity.get("job_name", hit.get("job_name", "")),
            "job_category": entity.get("job_category", hit.get("job_category", "")),
            "industry": entity.get("industry", hit.get("industry", "")),
            "content": entity.get("content", hit.get("content", "")),
            "row_index": entity.get("row_index", hit.get("row_index")),
            "sheet_name": entity.get("sheet_name", hit.get("sheet_name", "")),
            "source_file": entity.get("source_file", hit.get("source_file", "")),
            "metadata": metadata,
        }
