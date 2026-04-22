from __future__ import annotations

import base64
from http.client import RemoteDisconnected
import json
import re
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import get_settings
from app.services.resume_content_formatter import ResumeContentFormatter


class ResumeParserService:
    """Resume parser with document extraction, image OCR, and multimodal parsing."""

    image_types = {"png", "jpg", "jpeg", "webp", "bmp"}
    document_types = {"pdf", "doc", "docx"}
    word_types = {"doc", "docx"}
    supported_types = image_types | document_types

    def __init__(
        self,
        text_model: str | None = None,
        vision_model: str | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.DASHSCOPE_API_KEY or settings.OPENAI_API_KEY
        self.base_url = (base_url if base_url is not None else settings.LANGCHAIN_BASE_URL).rstrip("/")
        self.text_model = text_model or settings.LANGCHAIN_MODEL
        self.vision_model = vision_model or settings.RESUME_VISION_MODEL
        self.ocr_lang = settings.RESUME_OCR_LANG

    def parse(self, file_name: str, file_path: str) -> dict[str, Any]:
        path = Path(file_path)
        file_type = (path.suffix or Path(file_name).suffix).replace(".", "").lower()
        raw_text = ""
        engine = "unsupported"
        structured: dict[str, Any] | None = None
        parser_failed = False
        parser_failure_reason = ""

        if file_type in self.image_types:
            raw_text = self._extract_text_from_image(path)
            structured = self._parse_with_multimodal(path, raw_text)
            engine = "dashscope-vision" if structured else "local-ocr"
            if not structured and not raw_text.strip():
                parser_failed = True
                parser_failure_reason = "image_text_extraction_failed"
        elif file_type in self.document_types:
            raw_text = self._extract_text_from_document(path, file_type)
            if file_type in self.word_types and not raw_text.strip():
                parser_failed = True
                parser_failure_reason = "word_text_extraction_failed"
            structured = self._parse_with_text_llm(raw_text)
            engine = "dashscope-text" if structured else "document-text"
            if not structured and not raw_text.strip() and not parser_failure_reason:
                parser_failed = True
                parser_failure_reason = "document_text_extraction_failed"
        else:
            parser_failed = True
            parser_failure_reason = "unsupported_file_type"

        parsed_result = structured or self._build_raw_text_result(file_name, raw_text)

        normalized = self._normalize_result(
            parsed_result,
            file_name=file_name,
            file_path=file_path,
            file_type=file_type,
            raw_text=raw_text,
            engine=engine,
            parser_failed=parser_failed,
            parser_failure_reason=parser_failure_reason,
        )
        return normalized

    @staticmethod
    def is_low_quality(parsed: dict[str, Any], *, attachment_chain: bool = True) -> bool:
        if not isinstance(parsed, dict):
            return True
        if bool(parsed.get("parser_failed")):
            return True
        if parsed.get("parser_success") is False:
            return True
        return False

    def _extract_text_from_document(self, path: Path, file_type: str) -> str:
        if file_type == "pdf":
            return self._extract_text_from_pdf(path)
        if file_type == "doc":
            return self._extract_text_from_doc(path)
        if file_type == "docx":
            return self._extract_text_from_docx(path)
        return ""

    def _extract_text_from_pdf(self, path: Path) -> str:
        try:
            import fitz
        except ImportError:
            return ""

        fragments: list[str] = []
        try:
            with fitz.open(path) as document:
                for page in document:
                    text = page.get_text("text")
                    if text:
                        fragments.append(text)
        except Exception:
            return ""
        return "\n".join(fragments).strip()

    def _extract_text_from_docx(self, path: Path) -> str:
        try:
            from docx import Document
        except ImportError:
            return ""

        try:
            document = Document(str(path))
        except Exception:
            return ""
        return "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text).strip()

    def _extract_text_from_doc(self, path: Path) -> str:
        try:
            import textract
        except ImportError:
            return ""

        try:
            extracted = textract.process(str(path))
        except Exception:
            return ""

        if isinstance(extracted, bytes):
            for encoding in ("utf-8", "gb18030", "latin1"):
                try:
                    text = extracted.decode(encoding).strip()
                except UnicodeDecodeError:
                    continue
                if text:
                    return text
            return ""
        return str(extracted).strip()

    def _extract_text_from_image(self, path: Path) -> str:
        try:
            from PIL import Image
            import pytesseract
        except ImportError:
            return ""

        try:
            return pytesseract.image_to_string(Image.open(path), lang=self.ocr_lang).strip()
        except Exception:
            return ""

    def _parse_with_text_llm(self, raw_text: str) -> dict[str, Any] | None:
        if not self.api_key or not raw_text.strip():
            return None

        prompt = (
            "你是大学生简历结构化解析助手。"
            "请从以下简历文本中提取结构化 JSON，不要输出任何解释。"
            "JSON 字段必须包含："
            "name, phone, email, grade, major, college, target_role, target_industry, target_city, "
            "bio, summary, education_experience, interests, skills, certificates, projects, internships, "
            "competitions, campus_experiences, github, links。"
            "其中 projects 每项包含 name, role, description, technologies, outcome, start_date, end_date, relevance_score；"
            "internships 每项包含 company, position, description, skills, start_date, end_date, relevance_score；"
            "competitions 每项包含 name, award, level, description；"
            "campus_experiences 每项包含 title, role, description, duration。"
            "无法判断的字段请给空字符串、空数组或 null，不要编造。"
            "\n\n简历文本如下：\n"
            f"{raw_text[:12000]}"
        )
        return self._call_chat_completion(
            model=self.text_model,
            messages=[
                {"role": "system", "content": "你只输出合法 JSON。"},
                {"role": "user", "content": prompt},
            ],
        )

    def _parse_with_multimodal(self, path: Path, raw_text: str) -> dict[str, Any] | None:
        if not self.api_key:
            return None

        mime_type = self._mime_type(path.suffix.replace(".", "").lower())
        image_b64 = self._file_to_base64(path)
        if not image_b64:
            return None

        prompt = (
            "你是大学生简历多模态解析助手。请直接识别这张简历图片，并输出结构化 JSON，不要输出任何解释。"
            "JSON 字段必须包含：name, phone, email, grade, major, college, target_role, target_industry, target_city, "
            "bio, summary, education_experience, interests, skills, certificates, projects, internships, competitions, campus_experiences, github, links。"
            "projects / internships / competitions / campus_experiences 的字段要求与常规简历解析一致。"
            "如果 OCR 文本可辅助理解，可参考这段文本："
            f"{raw_text[:3000] if raw_text else '无本地 OCR 文本'}"
        )
        return self._call_chat_completion(
            model=self.vision_model,
            messages=[
                {"role": "system", "content": "你只输出合法 JSON。"},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
                    ],
                },
            ],
        )

    def _call_chat_completion(self, model: str, messages: list[dict[str, Any]]) -> dict[str, Any] | None:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        request = Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:
                raw_data = response.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError, ValueError, RemoteDisconnected):
            return None

        try:
            body = json.loads(raw_data)
        except json.JSONDecodeError:
            return None
        content = (((body.get("choices") or [{}])[0]).get("message") or {}).get("content")
        if isinstance(content, list):
            content = "".join(item.get("text", "") for item in content if isinstance(item, dict))
        return self._safe_load_json(content)

    def _safe_load_json(self, content: Any) -> dict[str, Any] | None:
        if not content:
            return None
        if isinstance(content, dict):
            return content

        text = str(content).strip()
        fenced = re.search(r"```json\s*(\{.*\})\s*```", text, re.S)
        if fenced:
            text = fenced.group(1).strip()
        elif text.startswith("```"):
            text = text.strip("`").strip()

        if not text.startswith("{"):
            first = text.find("{")
            last = text.rfind("}")
            if first >= 0 and last > first:
                text = text[first : last + 1]

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    def _build_raw_text_result(self, file_name: str, raw_text: str) -> dict[str, Any]:
        github = ResumeContentFormatter.extract_github(raw_text)
        return {
            "name": Path(file_name).stem,
            "summary": raw_text[:1200],
            "bio": raw_text[:1200],
            "phone": ResumeContentFormatter.extract_phone(raw_text),
            "email": ResumeContentFormatter.extract_email(raw_text),
            "github": github,
            "links": [github] if github else [],
            "grade": "",
            "major": "",
            "college": "",
            "target_role": "",
            "target_industry": "",
            "target_city": "",
            "education_experience": "",
            "interests": [],
            "skills": [],
            "certificates": [],
            "projects": [],
            "internships": [],
            "competitions": [],
            "campus_experiences": [],
        }

    def _normalize_result(
        self,
        parsed: dict[str, Any],
        *,
        file_name: str,
        file_path: str,
        file_type: str,
        raw_text: str,
        engine: str,
        parser_failed: bool = False,
        parser_failure_reason: str = "",
    ) -> dict[str, Any]:
        base_name = Path(file_name).stem
        summary = self._clean_scalar(parsed.get("summary") or parsed.get("bio")) or "已完成简历识别，可将识别结果同步到学生档案并自动生成能力画像。"
        phone = self._clean_scalar(parsed.get("phone")) or ResumeContentFormatter.extract_phone(raw_text)
        email = self._clean_scalar(parsed.get("email")) or ResumeContentFormatter.extract_email(raw_text)
        github = self._clean_scalar(parsed.get("github")) or ResumeContentFormatter.extract_github(raw_text)
        links = ResumeContentFormatter.normalize_links(
            github=github,
            links=parsed.get("links"),
            raw_text=raw_text,
        )

        return {
            "name": self._clean_scalar(parsed.get("name")) or base_name,
            "phone": phone,
            "email": email,
            "github": github,
            "links": links,
            "grade": self._clean_scalar(parsed.get("grade")),
            "major": self._clean_scalar(parsed.get("major")),
            "college": self._clean_scalar(parsed.get("college")),
            "target_role": self._clean_scalar(parsed.get("target_role")),
            "target_industry": self._clean_scalar(parsed.get("target_industry")),
            "target_city": self._clean_scalar(parsed.get("target_city")),
            "bio": self._clean_scalar(parsed.get("bio")),
            "summary": summary,
            "education_experience": ResumeContentFormatter.format_education(parsed.get("education_experience")),
            "interests": self._normalize_string_list(parsed.get("interests")),
            "skills": self._normalize_string_list(parsed.get("skills")),
            "certificates": self._normalize_string_list(parsed.get("certificates")),
            "projects": self._normalize_projects(parsed.get("projects")),
            "internships": self._normalize_internships(parsed.get("internships")),
            "competitions": self._normalize_competitions(parsed.get("competitions")),
            "campus_experiences": self._normalize_campus_experiences(parsed.get("campus_experiences")),
            "raw_text_preview": (raw_text or "")[:1500],
            "raw_text_length": len(raw_text or ""),
            "parser_engine": engine,
            "parser_mode": "image" if file_type in self.image_types else "document",
            "parser_failed": bool(parser_failed),
            "parser_failure_reason": parser_failure_reason,
            "parser_success": not bool(parser_failed),
            "file_name": file_name,
            "file_path": file_path,
            "file_type": file_type,
        }

    @staticmethod
    def _clean_scalar(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _normalize_string_list(self, value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, str):
            value = re.split(r"[,，/、;\n]+", value)
        result = []
        seen = set()
        for item in value:
            text = str(item).strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(text)
        return result

    def _normalize_projects(self, value: Any) -> list[dict[str, Any]]:
        items = value if isinstance(value, list) else [value] if value else []
        normalized = []
        for item in items[:8]:
            if isinstance(item, str):
                normalized.append(
                    {
                        "name": item.strip(),
                        "role": "",
                        "description": "",
                        "technologies": [],
                        "outcome": "",
                        "start_date": "",
                        "end_date": "",
                        "relevance_score": 80,
                    }
                )
                continue
            if not isinstance(item, dict):
                continue
            name = self._clean_scalar(item.get("name"))
            if not name:
                continue
            normalized.append(
                {
                    "name": name,
                    "role": self._clean_scalar(item.get("role")),
                    "description": self._clean_scalar(item.get("description")),
                    "technologies": self._normalize_string_list(item.get("technologies")),
                    "outcome": self._clean_scalar(item.get("outcome")),
                    "start_date": self._clean_scalar(item.get("start_date")),
                    "end_date": self._clean_scalar(item.get("end_date")),
                    "relevance_score": float(item.get("relevance_score") or 80),
                }
            )
        return normalized

    def _normalize_internships(self, value: Any) -> list[dict[str, Any]]:
        items = value if isinstance(value, list) else [value] if value else []
        normalized = []
        for item in items[:6]:
            if not isinstance(item, dict):
                continue
            company = self._clean_scalar(item.get("company"))
            position = self._clean_scalar(item.get("position"))
            if not company and not position:
                continue
            normalized.append(
                {
                    "company": company or "未识别公司",
                    "position": position or "实习岗位",
                    "description": self._clean_scalar(item.get("description")),
                    "skills": self._normalize_string_list(item.get("skills")),
                    "start_date": self._clean_scalar(item.get("start_date")),
                    "end_date": self._clean_scalar(item.get("end_date")),
                    "relevance_score": float(item.get("relevance_score") or 80),
                }
            )
        return normalized

    def _normalize_competitions(self, value: Any) -> list[dict[str, Any]]:
        items = value if isinstance(value, list) else [value] if value else []
        normalized = []
        for item in items[:6]:
            if isinstance(item, str):
                normalized.append({"name": item.strip(), "award": "", "level": "", "description": ""})
                continue
            if not isinstance(item, dict):
                continue
            name = self._clean_scalar(item.get("name"))
            if not name:
                continue
            normalized.append(
                {
                    "name": name,
                    "award": self._clean_scalar(item.get("award")),
                    "level": self._clean_scalar(item.get("level")),
                    "description": self._clean_scalar(item.get("description")),
                }
            )
        return normalized

    def _normalize_campus_experiences(self, value: Any) -> list[dict[str, Any]]:
        items = value if isinstance(value, list) else [value] if value else []
        normalized = []
        for item in items[:6]:
            if isinstance(item, str):
                normalized.append({"title": item.strip(), "role": "", "description": "", "duration": ""})
                continue
            if not isinstance(item, dict):
                continue
            title = self._clean_scalar(item.get("title"))
            if not title:
                continue
            normalized.append(
                {
                    "title": title,
                    "role": self._clean_scalar(item.get("role")),
                    "description": self._clean_scalar(item.get("description")),
                    "duration": self._clean_scalar(item.get("duration")),
                }
            )
        return normalized

    @staticmethod
    def _file_to_base64(path: Path) -> str:
        try:
            return base64.b64encode(path.read_bytes()).decode("utf-8")
        except OSError:
            return ""

    @staticmethod
    def _mime_type(file_type: str) -> str:
        return {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
            "bmp": "image/bmp",
        }.get(file_type, "image/png")


