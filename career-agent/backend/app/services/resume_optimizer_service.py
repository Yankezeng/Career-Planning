from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.models.job import Job, JobMatchResult
from app.models.student import Student, StudentAttachment
from app.services.resume_content_formatter import ResumeContentFormatter
from app.services.resume_optimization_engine import ResumeOptimizationEngine
from app.services.resume_parser_service import ResumeParserService
from app.services.resume_render_service import ResumeRenderService
from app.services.structured_llm_service import StructuredLLMService, get_structured_llm_service
from app.services.resume_version_service import ResumeVersionService
from app.utils.upload_paths import resolve_upload_reference, upload_path_to_url


class ResumeOptimizerService:
    def __init__(
        self,
        db: Session,
        resume_parser: ResumeParserService | None = None,
        renderer: ResumeRenderService | None = None,
        optimization_engine: ResumeOptimizationEngine | None = None,
        structured_llm_service: StructuredLLMService | None = None,
    ):
        self.db = db
        self.settings = get_settings()
        self.resume_parser = resume_parser or ResumeParserService()
        self.renderer = renderer or ResumeRenderService()
        self.optimization_engine = optimization_engine or ResumeOptimizationEngine()
        if structured_llm_service is not None:
            self.structured_llm_service = structured_llm_service
        else:
            try:
                self.structured_llm_service = get_structured_llm_service()
            except Exception:
                self.structured_llm_service = None

    def optimize_resume(self, student_id: int, attachment_id: int, options: dict[str, Any] | None = None) -> dict[str, Any]:
        context = self._build_context(student_id, attachment_id, options=options)
        student = context["student"]
        attachment = context["attachment"]
        parsed_resume = context["parsed_resume"]
        target_role = context["target_role"]

        optimization = self._build_optimization_bundle(context)
        merged_context = {**context, **optimization}
        word_path = self._generate_word_document(merged_context)
        pdf_path = self._generate_pdf_document(merged_context)
        word_url = self._to_upload_url(word_path)
        pdf_url = self._to_upload_url(pdf_path)
        preview_payload = self.get_pdf_preview_images(student_id, attachment.id)

        return {
            **optimization,
            "student_id": student.id,
            "attachment_id": attachment.id,
            "attachment_name": attachment.file_name,
            "target_role": target_role,
            "parsed_resume": parsed_resume,
            "editable_word_url": word_url,
            "editable_word_path": str(word_path),
            "optimized_pdf_url": pdf_url,
            "optimized_pdf_path": str(pdf_path),
            "artifacts": self._build_export_artifacts(
                attachment_name=attachment.file_name,
                word_url=word_url,
                pdf_url=pdf_url,
            ),
            "preview_supported": bool(preview_payload.get("supported")),
            "preview_message": str(preview_payload.get("message") or ""),
            "preview_images": preview_payload.get("preview_images") or [],
        }

    def export_editable_word(self, student_id: int, attachment_id: int, options: dict[str, Any] | None = None) -> Path:
        context = self._build_context(student_id, attachment_id, options=options)
        optimization = self._build_optimization_bundle(context)
        return self._generate_word_document({**context, **optimization})

    def export_pdf(self, student_id: int, attachment_id: int, options: dict[str, Any] | None = None) -> Path:
        context = self._build_context(student_id, attachment_id, options=options)
        optimization = self._build_optimization_bundle(context)
        return self._generate_pdf_document({**context, **optimization})

    def get_pdf_preview_images(self, student_id: int, attachment_id: int) -> dict[str, Any]:
        attachment = self._get_attachment(student_id, attachment_id)
        file_path = self._attachment_file_path(attachment)
        if file_path.suffix.lower() != ".pdf":
            message = "当前附件不是 PDF，暂不支持预览。"
            return {
                "attachment_id": attachment.id,
                "attachment_name": attachment.file_name,
                "supported": False,
                "message": message,
                "images": [],
                "preview_images": [],
                "image_items": [],
            }

        try:
            import fitz  # type: ignore
        except Exception:
            message = "PDF 预览依赖缺失，请安装 PyMuPDF（fitz）。"
            return {
                "attachment_id": attachment.id,
                "attachment_name": attachment.file_name,
                "supported": False,
                "message": message,
                "images": [],
                "preview_images": [],
                "image_items": [],
            }

        output_dir = self.settings.upload_path / "resume_previews" / f"student_{student_id}" / f"attachment_{attachment.id}"
        output_dir.mkdir(parents=True, exist_ok=True)

        image_items: list[dict[str, Any]] = []
        try:
            with fitz.open(file_path) as pdf:
                max_pages = min(5, len(pdf))
                for page_index in range(max_pages):
                    page = pdf[page_index]
                    pix = page.get_pixmap(dpi=144, alpha=False)
                    image_path = output_dir / f"page_{page_index + 1}.png"
                    pix.save(str(image_path))
                    image_items.append({"index": page_index + 1, "url": self._to_upload_url(image_path)})
        except Exception as exc:
            return {
                "attachment_id": attachment.id,
                "attachment_name": attachment.file_name,
                "supported": False,
                "message": f"PDF 预览生成失败：{exc}",
                "images": [],
                "preview_images": [],
                "image_items": [],
            }

        image_urls = [item["url"] for item in image_items]
        message = (
            f"已生成 {len(image_urls)} 页预览。"
            if image_urls
            else "该 PDF 未提取到可预览页面。"
        )
        return {
            "attachment_id": attachment.id,
            "attachment_name": attachment.file_name,
            "supported": bool(image_urls),
            "message": message,
            "images": image_urls,
            "preview_images": image_urls,
            "image_items": image_items,
        }

    def _build_context(self, student_id: int, attachment_id: int, options: dict[str, Any] | None = None) -> dict[str, Any]:
        student = (
            self.db.query(Student)
            .options(
                joinedload(Student.skills),
                joinedload(Student.certificates),
                joinedload(Student.projects),
                joinedload(Student.internships),
                joinedload(Student.competitions),
                joinedload(Student.campus_experiences),
                joinedload(Student.profiles),
            )
            .filter(Student.id == student_id, Student.deleted.is_(False))
            .first()
        )
        if not student:
            raise HTTPException(status_code=404, detail="student not found")

        options = options or {}
        attachment = self._get_attachment(student_id, attachment_id)
        file_path = self._attachment_file_path(attachment)

        version_service = ResumeVersionService(self.db)
        parsed_resume = version_service.get_cached_parsed_resume(
            student_id=student_id,
            attachment_id=attachment.id,
            options=options,
        )
        if not parsed_resume:
            parsed_resume = self.resume_parser.parse(attachment.file_name, str(file_path))
            if self.resume_parser.is_low_quality(parsed_resume or {}, attachment_chain=True):
                raise HTTPException(
                    status_code=422,
                    detail="resume parse quality is too low; please upload a clearer PDF/image or provide resume text and retry",
                )
            version_service.store_parsed_resume(
                student_id=student_id,
                attachment=attachment,
                parsed_resume=parsed_resume,
            )

        profile = self._get_latest_profile(student)
        target_role = self._get_target_role(student_id, student, profile, parsed_resume, options=options)
        target_job = self._get_target_job(student_id, target_role, options=options)
        return {
            "student": student,
            "attachment": attachment,
            "file_path": file_path,
            "parsed_resume": parsed_resume,
            "profile": profile,
            "target_role": target_role,
            "target_job": target_job,
            "options": options,
        }

    def _build_optimization_bundle(self, context: dict[str, Any]) -> dict[str, Any]:
        baseline = self._build_optimization(
            student=context["student"],
            target_role=context["target_role"],
            parsed_resume=context["parsed_resume"],
            target_job=context.get("target_job"),
            options=context.get("options") or {},
        )
        baseline_document = self._build_resume_document({**context, **baseline})
        llm_result, llm_meta, llm_error = self._run_deep_resume_optimization(
            context=context,
            baseline=baseline,
            baseline_document=baseline_document,
        )

        llm_success = bool(llm_result) and not llm_error
        merged = dict(baseline)
        if llm_success:
            for key in (
                "optimized_summary",
                "optimized_projects",
                "optimized_internships",
                "highlights",
                "issues",
                "recommended_keywords",
            ):
                value = llm_result.get(key)
                if self._is_non_empty_value(value):
                    merged[key] = deepcopy(value)

        merged_document = self._merge_resume_document(
            baseline_document=baseline_document,
            llm_document=llm_result.get("optimized_resume_document") if llm_success else {},
        )
        if str(merged.get("optimized_summary") or "").strip():
            merged_document["summary"] = str(merged.get("optimized_summary") or "").strip()
        if self._normalize_string_list(merged.get("highlights")):
            merged_document["highlights"] = self._normalize_string_list(merged.get("highlights"))
        if self._normalize_string_list(merged.get("issues")):
            merged_document["issues"] = self._normalize_string_list(merged.get("issues"))
        if self._normalize_string_list(merged.get("recommended_keywords")):
            merged_document["recommended_keywords"] = self._normalize_string_list(merged.get("recommended_keywords"))

        merged["optimized_resume_document"] = merged_document
        merged["optimized_resume_markdown"] = self._resume_document_markdown(merged_document)
        merged["llm_used"] = bool(llm_success)
        merged["optimization_mode"] = "llm+rule" if llm_success else "rule_only"
        merged["llm_meta"] = self._extract_llm_meta(meta=llm_meta, success=llm_success, error_message=llm_error)
        return merged

    def _run_deep_resume_optimization(
        self,
        *,
        context: dict[str, Any],
        baseline: dict[str, Any],
        baseline_document: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], str]:
        options = context.get("options") or {}
        if options.get("enable_deep_optimization") is False:
            return {}, {}, "disabled"
        if self.structured_llm_service is None:
            return {}, {}, "llm_unavailable"

        payload = self._build_deep_optimization_payload(
            context=context,
            baseline=baseline,
            baseline_document=baseline_document,
        )
        try:
            result = self.structured_llm_service.optimize_resume_content(payload)
            meta = self.structured_llm_service.get_last_call_meta() or {}
        except Exception as exc:
            meta = self.structured_llm_service.get_last_call_meta() or {}
            return {}, meta, str(exc)

        if not isinstance(result, dict):
            return {}, meta, "invalid_llm_result"

        has_effective_content = any(
            self._is_non_empty_value(result.get(key))
            for key in ("optimized_summary", "optimized_projects", "optimized_internships", "optimized_resume_document")
        )
        if not has_effective_content:
            return {}, meta, "empty_llm_result"

        return result, meta, ""

    def _build_deep_optimization_payload(
        self,
        *,
        context: dict[str, Any],
        baseline: dict[str, Any],
        baseline_document: dict[str, Any],
    ) -> dict[str, Any]:
        student = context.get("student")
        parsed_resume = context.get("parsed_resume") or {}
        target_job = context.get("target_job")
        target_job_snapshot = {}
        if target_job is not None:
            target_job_snapshot = {
                "id": getattr(target_job, "id", None),
                "name": str(getattr(target_job, "name", "") or "").strip(),
                "category": str(getattr(target_job, "category", "") or "").strip(),
                "industry": str(getattr(target_job, "industry", "") or "").strip(),
                "description": str(getattr(target_job, "description", "") or "").strip(),
                "work_content": str(getattr(target_job, "work_content", "") or "").strip(),
                "core_skill_tags": self._normalize_string_list(getattr(target_job, "core_skill_tags", []) or []),
                "common_skill_tags": self._normalize_string_list(getattr(target_job, "common_skill_tags", []) or []),
                "certificate_tags": self._normalize_string_list(getattr(target_job, "certificate_tags", []) or []),
            }

        baseline_payload = {
            "optimized_summary": str(baseline.get("optimized_summary") or "").strip(),
            "optimized_projects": deepcopy(baseline.get("optimized_projects") or []),
            "optimized_internships": deepcopy(baseline.get("optimized_internships") or []),
            "highlights": self._normalize_string_list(baseline.get("highlights") or []),
            "issues": self._normalize_string_list(baseline.get("issues") or []),
            "recommended_keywords": self._normalize_string_list(baseline.get("recommended_keywords") or []),
            "optimized_resume_document": deepcopy(baseline_document),
        }

        return {
            "task": "resume_deep_optimization",
            "policy": {
                "name": "conservative_truth_only",
                "rules": [
                    "Do not fabricate new experiences, achievements, metrics, organizations, or timelines.",
                    "Only rewrite and restructure using facts from parsed_resume, target_job, and baseline.",
                    "If quantitative evidence is missing, keep the original qualitative result and do not output suggestion wording in resume fields.",
                ],
            },
            "target_role": str(context.get("target_role") or "").strip(),
            "target_job": target_job_snapshot,
            "parsed_resume": deepcopy(parsed_resume),
            "student_profile": {"student_id": getattr(student, "id", None)},
            "baseline": baseline_payload,
            "required_output": {
                "optimized_summary": "string",
                "optimized_projects": "list",
                "optimized_internships": "list",
                "highlights": "list",
                "issues": "list",
                "recommended_keywords": "list",
                "optimized_resume_document": "object — MUST contain only pure resume content for direct submission. No explanatory, advisory, or instructional text in any field value. No \u5efa\u8bae/\u91cd\u70b9/\u6ce8\u610f/\u9700\u8981/\u5e94\u8be5/suggest/recommend/note/important/should patterns. Each field must be formal professional text.",
            },
        }

    def _merge_resume_document(self, *, baseline_document: dict[str, Any], llm_document: dict[str, Any] | None) -> dict[str, Any]:
        merged = deepcopy(baseline_document or {})
        llm_document = llm_document if isinstance(llm_document, dict) else {}

        for field in (
            "title",
            "name",
            "target_role",
            "phone",
            "email",
            "github",
            "college",
            "major",
            "grade",
            "target_city",
            "summary",
            "education_experience",
        ):
            text = str(llm_document.get(field) or "").strip()
            if text:
                merged[field] = text

        for field in ("skills", "certificates", "links", "highlights", "issues", "recommended_keywords"):
            values = self._normalize_string_list(llm_document.get(field))
            if values:
                merged[field] = values

        projects = self._normalize_projects_for_document(llm_document.get("projects"))
        if projects:
            merged["projects"] = projects

        internships = self._normalize_internships_for_document(llm_document.get("internships"))
        if internships:
            merged["internships"] = internships

        competitions = self._normalize_competitions_for_document(llm_document.get("competitions"))
        if competitions:
            merged["competitions"] = competitions

        campus_experiences = self._normalize_campus_for_document(llm_document.get("campus_experiences"))
        if campus_experiences:
            merged["campus_experiences"] = campus_experiences

        merged.setdefault("skills", [])
        merged.setdefault("certificates", [])
        merged.setdefault("links", [])
        merged.setdefault("projects", [])
        merged.setdefault("internships", [])
        merged.setdefault("competitions", [])
        merged.setdefault("campus_experiences", [])
        merged.setdefault("highlights", [])
        merged.setdefault("issues", [])
        merged.setdefault("recommended_keywords", [])
        return merged

    @staticmethod
    def _normalize_string_list(value: Any) -> list[str]:
        if not value:
            return []
        rows = value if isinstance(value, list) else [value]
        normalized: list[str] = []
        for item in rows:
            text = str(item or "").strip()
            if text:
                normalized.append(text)
        return normalized

    def _normalize_projects_for_document(self, value: Any) -> list[dict[str, Any]]:
        rows = value if isinstance(value, list) else []
        normalized: list[dict[str, Any]] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            role = str(item.get("role") or "").strip()
            duration = str(item.get("duration") or "").strip()
            rewrite = str(item.get("rewrite") or "").strip()
            technologies = self._normalize_string_list(item.get("technologies"))
            if not any([name, role, duration, rewrite, technologies]):
                continue
            normalized.append(
                {
                    "name": name,
                    "role": role,
                    "duration": duration,
                    "technologies": technologies,
                    "rewrite": rewrite,
                }
            )
        return normalized[:8]

    def _normalize_internships_for_document(self, value: Any) -> list[dict[str, Any]]:
        rows = value if isinstance(value, list) else []
        normalized: list[dict[str, Any]] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            company = str(item.get("company") or "").strip()
            position = str(item.get("position") or "").strip()
            duration = str(item.get("duration") or "").strip()
            rewrite = str(item.get("rewrite") or "").strip()
            skills = self._normalize_string_list(item.get("skills"))
            if not any([company, position, duration, rewrite, skills]):
                continue
            normalized.append(
                {
                    "company": company,
                    "position": position,
                    "duration": duration,
                    "skills": skills,
                    "rewrite": rewrite,
                }
            )
        return normalized[:8]

    def _normalize_competitions_for_document(self, value: Any) -> list[dict[str, Any]]:
        rows = value if isinstance(value, list) else []
        normalized: list[dict[str, Any]] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            award = str(item.get("award") or "").strip()
            level = str(item.get("level") or "").strip()
            description = str(item.get("description") or "").strip()
            if not any([name, award, level, description]):
                continue
            normalized.append(
                {
                    "name": name,
                    "award": award,
                    "level": level,
                    "description": description,
                }
            )
        return normalized[:10]

    def _normalize_campus_for_document(self, value: Any) -> list[dict[str, Any]]:
        rows = value if isinstance(value, list) else []
        normalized: list[dict[str, Any]] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            role = str(item.get("role") or "").strip()
            duration = str(item.get("duration") or "").strip()
            description = str(item.get("description") or "").strip()
            if not any([title, role, duration, description]):
                continue
            normalized.append(
                {
                    "title": title,
                    "role": role,
                    "duration": duration,
                    "description": description,
                }
            )
        return normalized[:10]

    def _resume_document_markdown(self, resume_document: dict[str, Any]) -> str:
        title = str(resume_document.get("title") or "优化简历").strip()
        name = str(resume_document.get("name") or "").strip()
        header = f"# {name} - {title}" if name else f"# {title}"
        lines: list[str] = [header, ""]

        meta_rows = [
            ("目标岗位", resume_document.get("target_role")),
            ("电话", resume_document.get("phone")),
            ("邮箱", resume_document.get("email")),
            ("GitHub", resume_document.get("github")),
            ("学校", resume_document.get("college")),
            ("专业", resume_document.get("major")),
            ("年级", resume_document.get("grade")),
            ("目标城市", resume_document.get("target_city")),
        ]
        for label, value in meta_rows:
            text = str(value or "").strip()
            if text:
                lines.append(f"- {label}：{text}")
        links = self._normalize_string_list(resume_document.get("links"))
        for link in links:
            if link != str(resume_document.get("github") or "").strip():
                lines.append(f"- 链接：{link}")

        summary = str(resume_document.get("summary") or "").strip()
        if summary:
            lines.extend(["", "## 个人简介", summary])

        education_experience = str(resume_document.get("education_experience") or "").strip()
        if education_experience:
            lines.extend(["", "## 教育经历", education_experience])

        skills = self._normalize_string_list(resume_document.get("skills"))
        if skills:
            lines.extend(["", "## 核心技能", "、".join(skills)])

        certificates = self._normalize_string_list(resume_document.get("certificates"))
        if certificates:
            lines.extend(["", "## 证书"])
            lines.extend([f"- {item}" for item in certificates])

        projects = self._normalize_projects_for_document(resume_document.get("projects"))
        if projects:
            lines.extend(["", "## 项目经历"])
            for item in projects:
                title_line = self._join_non_empty(
                    "",
                    item.get("name"),
                    self._join_non_empty("", item.get("role"), item.get("duration"), sep=" | "),
                    sep=" - ",
                )
                if title_line:
                    lines.append(f"- {title_line}")
                rewrite = str(item.get("rewrite") or "").strip()
                if rewrite:
                    lines.append(f"  - {rewrite}")

        internships = self._normalize_internships_for_document(resume_document.get("internships"))
        if internships:
            lines.extend(["", "## 实习经历"])
            for item in internships:
                title_line = self._join_non_empty(
                    "",
                    item.get("company"),
                    self._join_non_empty("", item.get("position"), item.get("duration"), sep=" | "),
                    sep=" - ",
                )
                if title_line:
                    lines.append(f"- {title_line}")
                rewrite = str(item.get("rewrite") or "").strip()
                if rewrite:
                    lines.append(f"  - {rewrite}")

        competitions = self._normalize_competitions_for_document(resume_document.get("competitions"))
        if competitions:
            lines.extend(["", "## 竞赛经历"])
            for item in competitions:
                title_line = self._join_non_empty(
                    "",
                    item.get("name"),
                    self._join_non_empty("", item.get("award"), item.get("level"), sep=" | "),
                    sep=" - ",
                )
                if title_line:
                    lines.append(f"- {title_line}")
                description = str(item.get("description") or "").strip()
                if description:
                    lines.append(f"  - {description}")

        campus_experiences = self._normalize_campus_for_document(resume_document.get("campus_experiences"))
        if campus_experiences:
            lines.extend(["", "## 校园经历"])
            for item in campus_experiences:
                title_line = self._join_non_empty(
                    "",
                    item.get("title"),
                    self._join_non_empty("", item.get("role"), item.get("duration"), sep=" | "),
                    sep=" - ",
                )
                if title_line:
                    lines.append(f"- {title_line}")
                description = str(item.get("description") or "").strip()
                if description:
                    lines.append(f"  - {description}")

        highlights = self._normalize_string_list(resume_document.get("highlights"))
        if highlights:
            lines.extend(["", "## 亮点总结"])
            lines.extend([f"- {item}" for item in highlights])

        issues = self._normalize_string_list(resume_document.get("issues"))
        if issues:
            lines.extend(["", "## 待补强项"])
            lines.extend([f"- {item}" for item in issues])

        keywords = self._normalize_string_list(resume_document.get("recommended_keywords"))
        if keywords:
            lines.extend(["", "## 关键词建议", "、".join(keywords)])

        return "\n".join(lines).strip()

    @staticmethod
    def _join_non_empty(prefix: str, *values: Any, sep: str = "") -> str:
        parts = [str(item).strip() for item in values if str(item or "").strip()]
        if not parts:
            return ""
        body = sep.join(parts) if sep else "".join(parts)
        return f"{prefix}{body}" if prefix else body

    @staticmethod
    def _is_non_empty_value(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, dict, set)):
            return bool(value)
        return True

    @staticmethod
    def _extract_llm_meta(*, meta: dict[str, Any], success: bool, error_message: str) -> dict[str, Any]:
        meta = meta or {}
        return {
            "provider": str(meta.get("provider") or ""),
            "model_name": str(meta.get("model_name") or ""),
            "status": str(meta.get("status") or ("success" if success else "failed")),
            "latency_ms": float(meta.get("latency_ms") or 0),
            "prompt_tokens": int(meta.get("prompt_tokens") or 0),
            "completion_tokens": int(meta.get("completion_tokens") or 0),
            "total_tokens": int(meta.get("total_tokens") or 0),
            "error_message": str(meta.get("error_message") or error_message or ""),
        }

    def _get_attachment(self, student_id: int, attachment_id: int) -> StudentAttachment:
        attachment = (
            self.db.query(StudentAttachment)
            .filter(
                StudentAttachment.id == attachment_id,
                StudentAttachment.student_id == student_id,
                StudentAttachment.deleted.is_(False),
            )
            .first()
        )
        if not attachment:
            raise HTTPException(status_code=404, detail="attachment not found")
        return attachment

    def _attachment_file_path(self, attachment) -> Path:
        file_path = resolve_upload_reference(
            upload_root=self.settings.upload_path,
            reference=getattr(attachment, "file_path", ""),
            must_exist=True,
        )
        if not file_path:
            raise HTTPException(status_code=404, detail="resume file not found, please re-upload and retry")
        return file_path

    @staticmethod
    def _get_latest_profile(student):
        profiles = [item for item in (student.profiles or []) if not getattr(item, "deleted", False)]
        if not profiles:
            return None
        profiles.sort(key=lambda row: int(getattr(row, "id", 0) or 0), reverse=True)
        return profiles[0]

    def _get_target_role(self, student_id, student, profile, parsed_resume, options: dict[str, Any] | None = None):
        options = options or {}
        manual_target_role = str(options.get("target_role") or "").strip()
        if manual_target_role:
            return manual_target_role

        parsed_target = str((parsed_resume or {}).get("target_role") or "").strip()
        if parsed_target:
            return parsed_target

        match_row = (
            self.db.query(JobMatchResult)
            .join(Job, Job.id == JobMatchResult.job_id)
            .filter(JobMatchResult.student_id == student_id, JobMatchResult.deleted.is_(False), Job.deleted.is_(False))
            .order_by(JobMatchResult.total_score.desc(), JobMatchResult.id.desc())
            .first()
        )
        if match_row and getattr(match_row, "job", None):
            job_name = str(getattr(match_row.job, "name", "") or "").strip()
            if job_name:
                return job_name

        if profile and str(getattr(profile, "summary", "") or "").strip():
            summary = str(profile.summary).strip()
            if "鐩爣" in summary:
                return summary.split("鐩爣", 1)[-1][:20].strip("锛?锛?銆?")

        if str(student.target_industry or "").strip():
            return f"{student.target_industry}鐩稿叧宀椾綅"
        return "鐩爣宀椾綅"

    def _get_target_job(self, student_id: int, target_role: str, options: dict[str, Any] | None = None) -> Job | None:
        options = options or {}
        target_job_id = options.get("target_job_id")
        if target_job_id:
            try:
                job = (
                    self.db.query(Job)
                    .filter(Job.id == int(target_job_id), Job.deleted.is_(False))
                    .first()
                )
                if job:
                    return job
            except Exception:
                pass

        match_row = (
            self.db.query(JobMatchResult)
            .join(Job, Job.id == JobMatchResult.job_id)
            .filter(JobMatchResult.student_id == student_id, JobMatchResult.deleted.is_(False), Job.deleted.is_(False))
            .order_by(JobMatchResult.total_score.desc(), JobMatchResult.id.desc())
            .first()
        )
        if match_row and getattr(match_row, "job", None):
            return match_row.job

        target_role_text = str(target_role or "").strip()
        if target_role_text:
            return (
                self.db.query(Job)
                .filter(Job.deleted.is_(False), Job.name.ilike(f"%{target_role_text}%"))
                .order_by(Job.id.desc())
                .first()
            )
        return None

    def _build_optimization(
        self,
        *,
        student,
        target_role: str,
        parsed_resume: dict[str, Any],
        target_job: Job | None = None,
        options: dict[str, Any] | None = None,
    ):
        options = options or {}
        role_skills = parsed_resume.get("skills") or []
        recommended_keywords = self._recommend_keywords(
            target_role=target_role,
            skills=role_skills,
            parsed_resume=parsed_resume,
            target_job=target_job,
            options=options,
        )
        return self.optimization_engine.optimize(
            student=student,
            target_role=target_role,
            parsed_resume=parsed_resume,
            target_job=target_job,
            recommended_keywords=recommended_keywords,
            job_description_hint=str(options.get("job_description") or "").strip(),
        )

    def _recommend_keywords(
        self,
        target_role,
        skills,
        parsed_resume,
        target_job: Job | None = None,
        options: dict[str, Any] | None = None,
    ):
        options = options or {}
        return self.optimization_engine.recommend_keywords(
            target_role=str(target_role or ""),
            skills=[str(item).strip() for item in (skills or []) if str(item).strip()],
            parsed_resume=parsed_resume or {},
            target_job=target_job,
            job_description_hint=str(options.get("job_description") or "").strip(),
        )

    def _build_highlights(
        self,
        target_role,
        skills,
        certificates,
        project_count,
        internship_count,
        *,
        keyword_hit_count: int = 0,
        keyword_total: int = 0,
        quantifiable_points: int = 0,
    ):
        return self.optimization_engine.build_highlights(
            target_role=str(target_role or ""),
            skills=[str(item).strip() for item in (skills or []) if str(item).strip()],
            certificates=[str(item).strip() for item in (certificates or []) if str(item).strip()],
            project_count=int(project_count or 0),
            internship_count=int(internship_count or 0),
            keyword_hit_count=int(keyword_hit_count or 0),
            keyword_total=int(keyword_total or 0),
            quantifiable_points=int(quantifiable_points or 0),
        )

    def _build_issues(
        self,
        target_role,
        student,
        parsed_resume,
        *,
        projects: list[dict[str, Any]] | None = None,
        internships: list[dict[str, Any]] | None = None,
        skills: list[str] | None = None,
        missing_keywords: list[str] | None = None,
        quantifiable_points: int = 0,
    ):
        projects = projects or []
        internships = internships or []
        skills = [str(item).strip() for item in (skills or []) if str(item).strip()]
        return self.optimization_engine.build_issues(
            target_role=str(target_role or ""),
            parsed_resume=parsed_resume or {},
            student=student,
            projects=projects,
            internships=internships,
            skills=skills,
            missing_keywords=[str(item).strip() for item in (missing_keywords or []) if str(item).strip()],
            quantifiable_points=int(quantifiable_points or 0),
        )

    def _rewrite_project(self, name, role, technologies, outcome, target_role):
        return self.optimization_engine.rewrite_project(
            {
                "name": name,
                "role": role,
                "technologies": technologies or [],
                "outcome": outcome,
            },
            target_role=str(target_role or ""),
            jd_keywords=[],
        )

    def _rewrite_internship(self, company, position, skills, description, target_role):
        return self.optimization_engine.rewrite_internship(
            {
                "company": company,
                "position": position,
                "skills": skills or [],
                "description": description,
            },
            target_role=str(target_role or ""),
            jd_keywords=[],
        )

    def _build_resume_document(self, context: dict[str, Any]) -> dict[str, Any]:
        parsed_resume = context.get("parsed_resume") or {}
        optimized_projects = context.get("optimized_projects") or []
        optimized_internships = context.get("optimized_internships") or []

        if not optimized_projects:
            optimized_projects = [
                self._rewrite_project(
                    item.get("name"),
                    item.get("role"),
                    item.get("technologies") or [],
                    item.get("outcome"),
                    context.get("target_role"),
                )
                for item in (parsed_resume.get("projects") or [])
                if isinstance(item, dict)
            ]
        if not optimized_internships:
            optimized_internships = [
                self._rewrite_internship(
                    item.get("company"),
                    item.get("position"),
                    item.get("skills") or [],
                    item.get("description"),
                    context.get("target_role"),
                )
                for item in (parsed_resume.get("internships") or [])
                if isinstance(item, dict)
            ]

        skills = parsed_resume.get("skills") or []
        certificates = parsed_resume.get("certificates") or []
        competitions = parsed_resume.get("competitions") or []
        campus_experiences = parsed_resume.get("campus_experiences") or []
        github = str(parsed_resume.get("github") or "").strip()
        links = ResumeContentFormatter.normalize_links(
            github=github,
            links=parsed_resume.get("links"),
            raw_text=str(parsed_resume.get("raw_text_preview") or ""),
        )

        return {
            "title": "优化简历（可投递版）",
            "name": str(parsed_resume.get("name") or "").strip(),
            "target_role": str(context.get("target_role") or "").strip(),
            "phone": str(parsed_resume.get("phone") or "").strip(),
            "email": str(parsed_resume.get("email") or "").strip(),
            "github": github,
            "links": links,
            "college": str(parsed_resume.get("college") or "").strip(),
            "major": str(parsed_resume.get("major") or "").strip(),
            "grade": str(parsed_resume.get("grade") or "").strip(),
            "target_city": str(parsed_resume.get("target_city") or "").strip(),
            "summary": str(context.get("optimized_summary") or "").strip(),
            "education_experience": ResumeContentFormatter.format_education(parsed_resume.get("education_experience")),
            "skills": self._normalize_string_list(skills),
            "certificates": self._normalize_string_list(certificates),
            "projects": self._normalize_projects_for_document(optimized_projects),
            "internships": self._normalize_internships_for_document(optimized_internships),
            "competitions": self._normalize_competitions_for_document(competitions),
            "campus_experiences": self._normalize_campus_for_document(campus_experiences),
            "highlights": self._normalize_string_list(context.get("highlights") or []),
            "issues": self._normalize_string_list(context.get("issues") or []),
            "recommended_keywords": self._normalize_string_list(context.get("recommended_keywords") or []),
        }

    def _generate_word_document(self, context):
        student = context["student"]
        attachment = context["attachment"]
        output_dir = self.settings.upload_path / "resume_exports" / f"student_{student.id}"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"student_{student.id}_attachment_{attachment.id}_optimized_resume.docx"

        resume_document = deepcopy(context.get("optimized_resume_document") or {}) or self._build_resume_document(context)
        try:
            self.renderer.render_word(resume_document=resume_document, output_path=output_path)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=500, detail=f"word export failed: {exc}") from exc
        return output_path

    def _generate_pdf_document(self, context):
        student = context["student"]
        attachment = context["attachment"]
        output_dir = self.settings.upload_path / "resume_exports" / f"student_{student.id}"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"student_{student.id}_attachment_{attachment.id}_optimized_resume.pdf"

        resume_document = deepcopy(context.get("optimized_resume_document") or {}) or self._build_resume_document(context)
        try:
            self.renderer.render_pdf(resume_document=resume_document, output_path=output_path)
        except Exception as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=500, detail=f"pdf export failed: {exc}") from exc
        return output_path

    def _to_upload_url(self, path: Path) -> str:
        return upload_path_to_url(upload_root=self.settings.upload_path, absolute_path=path)

    @staticmethod
    def _build_export_artifacts(*, attachment_name: str, word_url: str, pdf_url: str) -> list[dict[str, Any]]:
        stem = Path(str(attachment_name or "optimized_resume")).stem or "optimized_resume"
        return [
            {
                "name": f"{stem}-优化版.docx",
                "type": "document",
                "download_url": word_url,
                "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            },
            {
                "name": f"{stem}-优化版.pdf",
                "type": "document",
                "download_url": pdf_url,
                "mime_type": "application/pdf",
            },
        ]
