from __future__ import annotations

import json
import re
from typing import Any

from app.core.config import get_settings
from app.services.llm_service import get_llm_service


settings = get_settings()


class ImageParser:
    def __init__(self):
        self.llm_service = get_llm_service()
        self.vision_model = settings.RESUME_VISION_MODEL
        self.ocr_lang = settings.RESUME_OCR_LANG

    def parse_resume_image(self, image_path: str) -> dict[str, Any]:
        try:
            import fitz
        except ImportError:
            return {"error": "PyMuPDF not available", "parsed": {}}

        try:
            doc = fitz.open(image_path)
            if doc.page_count == 0:
                return {"error": "Empty document", "parsed": {}}

            page = doc[0]
            text = page.get_text()

            if text.strip():
                return self._parse_text_resume(text)
            else:
                return {"error": "No text found in image", "parsed": {}}

        except Exception as e:
            return {"error": str(e), "parsed": {}}

    def _parse_text_resume(self, text: str) -> dict[str, Any]:
        parsed = {
            "name": self._extract_name(text),
            "phone": self._extract_phone(text),
            "email": self._extract_email(text),
            "education": self._extract_education(text),
            "experience": self._extract_experience(text),
            "skills": self._extract_skills(text),
            "raw_text": text[:500],
        }
        return parsed

    def _extract_name(self, text: str) -> str:
        lines = text.strip().split("\n")
        if lines:
            first_line = lines[0].strip()
            if len(first_line) <= 10 and not any(c in first_line for c in ["@", "电话", "手机", "邮箱", "：", ":"]):
                return first_line
        return ""

    def _extract_phone(self, text: str) -> str:
        patterns = [
            r"1[3-9]\d{9}",
            r"\d{3}[- ]?\d{4}[- ]?\d{4}",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group()
        return ""

    def _extract_email(self, text: str) -> str:
        pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        match = re.search(pattern, text)
        if match:
            return match.group()
        return ""

    def _extract_education(self, text: str) -> list[str]:
        education_keywords = ["本科", "硕士", "博士", "学士", "研究生", "大学", "学院", "学历"]
        education = []

        lines = text.split("\n")
        for line in lines:
            line_lower = line.lower()
            if any(kw in line for kw in education_keywords):
                cleaned = re.sub(r"\s+", " ", line.strip())
                if cleaned and len(cleaned) < 100:
                    education.append(cleaned)

        return education[:3]

    def _extract_experience(self, text: str) -> list[str]:
        experience_keywords = ["工作经历", "实习经历", "项目经验", "项目经历", "工作经验"]
        experience = []

        lines = text.split("\n")
        capturing = False
        for line in lines:
            if any(kw in line for kw in experience_keywords):
                capturing = True
                continue
            if capturing:
                if any(kw in line for kw in ["教育", "技能", "证书", "荣誉"]):
                    capturing = False
                    continue
                if line.strip():
                    experience.append(line.strip())
                    if len(experience) >= 5:
                        break

        return experience[:5]

    def _extract_skills(self, text: str) -> list[str]:
        skill_keywords = [
            "Python", "Java", "JavaScript", "Go", "C++", "C#", "Ruby", "PHP",
            "React", "Vue", "Angular", "Node.js", "Django", "Flask", "Spring",
            "SQL", "MySQL", "PostgreSQL", "MongoDB", "Redis",
            "TensorFlow", "PyTorch", "Keras",
            "AWS", "Azure", "Docker", "Kubernetes",
            "机器学习", "深度学习", "NLP", "数据分析",
        ]

        found_skills = []
        text_lower = text.lower()
        for skill in skill_keywords:
            if skill.lower() in text_lower:
                found_skills.append(skill)

        return list(dict.fromkeys(found_skills))[:10]

    def parse_with_vision(self, image_path: str) -> dict[str, Any]:
        prompt = """请分析这张简历图片，提取以下信息：
1. 姓名
2. 手机号码
3. 邮箱
4. 学历信息（学校、专业、学位、时间）
5. 工作/实习经历（公司、职位、时间、工作内容）
6. 技能（编程语言、框架、工具等）

请用JSON格式返回。"""

        try:
            response = self.llm_service.chat(
                user_role="system",
                user_name="assistant",
                message=f"请分析这张图片：{image_path}\n\n{prompt}",
                history=[],
                context={"scene": "vision_resume_parse"},
            )

            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]

            parsed = json.loads(response.strip())
            return {"parsed": parsed, "source": "vision"}

        except Exception as e:
            return {"error": str(e), "parsed": {}, "source": "vision"}


class DocumentParser:
    SUPPORTED_FORMATS = [".pdf", ".docx", ".doc", ".txt", ".md"]

    def __init__(self):
        self.image_parser = ImageParser()

    def parse(self, file_path: str) -> dict[str, Any]:
        import os
        ext = os.path.splitext(file_path)[1].lower()

        if ext not in self.SUPPORTED_FORMATS:
            return {"error": f"Unsupported format: {ext}", "parsed": {}}

        if ext == ".pdf":
            return self._parse_pdf(file_path)
        elif ext in [".docx", ".doc"]:
            return self._parse_word(file_path)
        elif ext in [".txt", ".md"]:
            return self._parse_text(file_path)

        return {"error": "Unknown error", "parsed": {}}

    def _parse_pdf(self, file_path: str) -> dict[str, Any]:
        try:
            import fitz
        except ImportError:
            return {"error": "PyMuPDF not available", "parsed": {}}

        try:
            doc = fitz.open(file_path)
            all_text = ""

            for page_num in range(doc.page_count):
                page = doc[page_num]
                text = page.get_text()
                all_text += text + "\n\n"

            parsed = self._extract_structured_info(all_text)
            return {"parsed": parsed, "source": "pdf", "page_count": doc.page_count}

        except Exception as e:
            return {"error": str(e), "parsed": {}}

    def _parse_word(self, file_path: str) -> dict[str, Any]:
        try:
            from docx import Document
        except ImportError:
            return {"error": "python-docx not available", "parsed": {}}

        try:
            doc = Document(file_path)
            all_text = "\n".join([p.text for p in doc.paragraphs])

            parsed = self._extract_structured_info(all_text)
            return {"parsed": parsed, "source": "docx"}

        except Exception as e:
            return {"error": str(e), "parsed": {}}

    def _parse_text(self, file_path: str) -> dict[str, Any]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()

            parsed = self._extract_structured_info(text)
            return {"parsed": parsed, "source": "text"}

        except Exception as e:
            return {"error": str(e), "parsed": {}}

    def _extract_structured_info(self, text: str) -> dict[str, Any]:
        image_parser = ImageParser()
        return image_parser._parse_text_resume(text)


def get_image_parser() -> ImageParser:
    return ImageParser()


def get_document_parser() -> DocumentParser:
    return DocumentParser()
