from __future__ import annotations

import ast
import re
from typing import Any


class ResumeContentFormatter:
    github_pattern = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?", re.I)
    email_pattern = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    phone_pattern = re.compile(r"(?:\+?86[-\s]?)?1[3-9]\d{9}")

    @classmethod
    def clean_text(cls, value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip())

    @classmethod
    def normalize_string_list(cls, value: Any) -> list[str]:
        if not value:
            return []
        rows = value
        if isinstance(value, str):
            rows = re.split(r"[,，/、;；\n]+", value)
        if isinstance(rows, dict):
            rows = rows.values()
        result: list[str] = []
        seen: set[str] = set()
        for item in rows:
            text = cls.clean_text(item)
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(text)
        return result

    @classmethod
    def extract_email(cls, raw_text: str) -> str:
        match = cls.email_pattern.search(raw_text or "")
        return match.group(0) if match else ""

    @classmethod
    def extract_phone(cls, raw_text: str) -> str:
        match = cls.phone_pattern.search(raw_text or "")
        return re.sub(r"[\s-]", "", match.group(0)).removeprefix("+86") if match else ""

    @classmethod
    def extract_github(cls, raw_text: str) -> str:
        match = cls.github_pattern.search(raw_text or "")
        if not match:
            return ""
        value = match.group(0).rstrip("。；;，,、")
        return value if value.startswith(("http://", "https://")) else f"https://{value}"

    @classmethod
    def normalize_links(cls, *, github: Any = "", links: Any = None, raw_text: str = "") -> list[str]:
        rows = cls.normalize_string_list(links)
        github_text = cls.clean_text(github) or cls.extract_github(raw_text)
        if github_text:
            github_text = github_text if github_text.startswith(("http://", "https://")) else f"https://{github_text}"
            rows.insert(0, github_text)
        result: list[str] = []
        seen: set[str] = set()
        for item in rows:
            text = cls.clean_text(item).rstrip("。；;，,、")
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(text)
        return result

    @classmethod
    def format_education(cls, value: Any) -> str:
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return ""
            if not (text.startswith("[") or text.startswith("{")):
                return "\n".join(line.strip() for line in text.splitlines() if line.strip()) or text
        rows = cls._education_rows(value)
        if not rows:
            return cls.clean_text(value)
        lines: list[str] = []
        for item in rows:
            if not isinstance(item, dict):
                text = cls.clean_text(item)
                if text:
                    lines.append(text)
                continue
            primary = cls._join_non_empty(
                [
                    item.get("institution") or item.get("school") or item.get("college"),
                    item.get("major"),
                    item.get("degree"),
                    item.get("duration") or cls._join_non_empty([item.get("start_date"), item.get("end_date")], " - "),
                ],
                " | ",
            )
            if primary:
                lines.append(primary)
            metrics = cls._join_non_empty([item.get("gpa"), item.get("rank"), item.get("honors")], " | ")
            if metrics:
                lines.append(metrics)
            courses = cls.normalize_string_list(item.get("courses") or item.get("core_courses"))
            if courses:
                lines.append(f"核心课程：{'、'.join(courses)}")
        return "\n".join(lines).strip()

    @classmethod
    def _education_rows(cls, value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            return [value]
        text = str(value or "").strip()
        if not text:
            return []
        if text.startswith("[") or text.startswith("{"):
            parsed = ast.literal_eval(text)
            return parsed if isinstance(parsed, list) else [parsed]
        return [text]

    @staticmethod
    def _join_non_empty(values: list[Any], sep: str) -> str:
        parts = [str(item).strip() for item in values if str(item or "").strip()]
        return sep.join(parts)
