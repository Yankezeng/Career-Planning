from __future__ import annotations

import re
from typing import Any


class ResumeOptimizationEngine:
    """Rule-based optimization engine with JD alignment, STAR rewrites, and explainable scoring."""

    _action_verbs = ("负责", "推动", "设计", "实现", "搭建", "优化", "提升", "协同", "落地", "分析", "复盘")
    _quant_pattern = re.compile(r"\d+(\.\d+)?\s*(%|％|k|K|w|W|万|千|次|人|条|个|天|周|月|年)")

    _role_keyword_map: dict[str, list[str]] = {
        "产品": ["需求分析", "用户研究", "PRD", "跨团队协作", "数据驱动"],
        "运营": ["用户增长", "活动策划", "内容运营", "数据分析", "转化优化"],
        "数据": ["Python", "SQL", "数据建模", "可视化", "A/B测试"],
        "前端": ["JavaScript", "TypeScript", "Vue", "React", "工程化"],
        "后端": ["Python", "Java", "接口设计", "数据库", "系统优化"],
        "测试": ["测试用例", "自动化测试", "缺陷分析", "质量保障"],
        "设计": ["Figma", "交互设计", "视觉表达", "设计系统"],
        "算法": ["机器学习", "特征工程", "模型评估", "Python", "深度学习"],
    }

    def optimize(
        self,
        *,
        student: Any,
        target_role: str,
        parsed_resume: dict[str, Any],
        target_job: Any | None = None,
        recommended_keywords: list[str] | None = None,
        job_description_hint: str = "",
    ) -> dict[str, Any]:
        parsed_resume = parsed_resume or {}
        skills = self._to_string_list(parsed_resume.get("skills"))
        certificates = self._to_string_list(parsed_resume.get("certificates"))
        projects = self._normalize_projects(parsed_resume.get("projects"))
        internships = self._normalize_internships(parsed_resume.get("internships"))

        recommended_keywords = self.recommend_keywords(
            target_role=target_role,
            skills=skills,
            parsed_resume=parsed_resume,
            target_job=target_job,
            job_description_hint=job_description_hint,
            fallback=recommended_keywords,
        )
        jd_keywords = recommended_keywords[:12]

        keyword_hit_count, missing_keywords = self._keyword_coverage(
            keywords=jd_keywords,
            parsed_resume=parsed_resume,
            skills=skills,
            projects=projects,
            internships=internships,
        )
        keyword_match_score = round((keyword_hit_count / max(len(jd_keywords), 1)) * 100, 1)

        content_richness_score = self._content_richness_score(parsed_resume, projects, internships, skills, certificates)
        project_evidence_score, quantifiable_points = self._evidence_score(projects, internships)
        role_alignment_score = self._role_alignment_score(target_role, jd_keywords, skills, projects, internships, target_job)
        expression_quality_score = self._expression_quality_score(parsed_resume, projects, internships)

        resume_score = round(
            keyword_match_score * 0.30
            + project_evidence_score * 0.26
            + content_richness_score * 0.18
            + role_alignment_score * 0.16
            + expression_quality_score * 0.10,
            1,
        )
        confidence = self._confidence_score(
            parsed_resume=parsed_resume,
            projects=projects,
            internships=internships,
            jd_keywords=jd_keywords,
            target_job=target_job,
        )

        rewritten_projects = [
            self.rewrite_project(item, target_role=target_role, jd_keywords=jd_keywords)
            for item in projects[:8]
        ]
        rewritten_internships = [
            self.rewrite_internship(item, target_role=target_role, jd_keywords=jd_keywords)
            for item in internships[:8]
        ]

        optimized_summary = self._rewrite_summary(
            original_summary=str(parsed_resume.get("summary") or parsed_resume.get("bio") or "").strip(),
            target_role=target_role,
            skills=skills,
            keyword_hit_count=keyword_hit_count,
            keyword_total=len(jd_keywords),
        )

        highlights = self.build_highlights(
            target_role=target_role,
            skills=skills,
            certificates=certificates,
            project_count=len(projects),
            internship_count=len(internships),
            keyword_hit_count=keyword_hit_count,
            keyword_total=len(jd_keywords),
            quantifiable_points=quantifiable_points,
        )
        issues = self.build_issues(
            target_role=target_role,
            parsed_resume=parsed_resume,
            student=student,
            projects=projects,
            internships=internships,
            skills=skills,
            missing_keywords=missing_keywords,
            quantifiable_points=quantifiable_points,
        )

        score_breakdown = [
            {"metric": "ATS关键词匹配", "score": keyword_match_score, "weight": 0.30, "reason": f"命中 {keyword_hit_count}/{max(len(jd_keywords), 1)}"},
            {"metric": "经历证据强度", "score": project_evidence_score, "weight": 0.26, "reason": f"量化表述 {quantifiable_points} 处"},
            {"metric": "内容完整度", "score": content_richness_score, "weight": 0.18, "reason": f"项目 {len(projects)} 段 / 实习 {len(internships)} 段"},
            {"metric": "岗位贴合度", "score": role_alignment_score, "weight": 0.16, "reason": f"目标岗位 {target_role}"},
            {"metric": "表达质量", "score": expression_quality_score, "weight": 0.10, "reason": "STAR 结构与行动动词覆盖"},
        ]

        return {
            "target_role": target_role,
            "resume_score": resume_score,
            "keyword_match_score": keyword_match_score,
            "content_richness_score": content_richness_score,
            "project_evidence_score": project_evidence_score,
            "recommended_keywords": jd_keywords,
            "keyword_hits": keyword_hit_count,
            "missing_keywords": missing_keywords[:8],
            "quantifiable_points": quantifiable_points,
            "confidence": confidence,
            "score_breakdown": score_breakdown,
            "highlights": highlights,
            "issues": issues,
            "optimized_summary": optimized_summary,
            "optimized_projects": rewritten_projects,
            "optimized_internships": rewritten_internships,
        }

    def recommend_keywords(
        self,
        *,
        target_role: str,
        skills: list[str],
        parsed_resume: dict[str, Any],
        target_job: Any | None = None,
        job_description_hint: str = "",
        fallback: list[str] | None = None,
    ) -> list[str]:
        role = str(target_role or "").lower()
        keywords: list[str] = []

        if target_job is not None:
            for field in ("core_skill_tags", "common_skill_tags", "certificate_tags"):
                values = getattr(target_job, field, None) or []
                keywords.extend(self._to_string_list(values))
            for field in ("description", "work_content", "major_requirement", "internship_requirement"):
                keywords.extend(self._extract_jd_tokens(str(getattr(target_job, field, "") or "")))

        if job_description_hint:
            keywords.extend(self._extract_jd_tokens(job_description_hint))

        for key, words in self._role_keyword_map.items():
            if key in role:
                keywords.extend(words)

        role_from_resume = str(parsed_resume.get("target_role") or "").strip()
        if role_from_resume:
            keywords.append(role_from_resume)

        if fallback:
            keywords.extend(self._to_string_list(fallback))

        # Use resume skills only as a weak supplement, avoid score inflation.
        keywords.extend(self._to_string_list(skills)[:4])

        deduped: list[str] = []
        seen: set[str] = set()
        for item in keywords:
            text = str(item or "").strip()
            if len(text) < 2:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(text)

        if not deduped:
            deduped = ["岗位理解", "项目实践", "成果量化", "协作沟通", "持续学习"]
        return deduped[:12]

    def build_highlights(
        self,
        *,
        target_role: str,
        skills: list[str],
        certificates: list[str],
        project_count: int,
        internship_count: int,
        keyword_hit_count: int,
        keyword_total: int,
        quantifiable_points: int,
    ) -> list[str]:
        rows = [
            f"简历目标岗位已聚焦为：{target_role}",
            f"JD 关键词命中率：{keyword_hit_count}/{max(keyword_total, 1)}",
            f"技能覆盖 {len(skills)} 项，证书资质 {len(certificates)} 项",
            f"项目经历 {project_count} 段，实习经历 {internship_count} 段",
            f"量化成果表述 {quantifiable_points} 处",
        ]
        return [item for item in rows if item]

    def build_issues(
        self,
        *,
        target_role: str,
        parsed_resume: dict[str, Any],
        student: Any,
        projects: list[dict[str, Any]],
        internships: list[dict[str, Any]],
        skills: list[str],
        missing_keywords: list[str],
        quantifiable_points: int,
    ) -> list[str]:
        issues: list[str] = []

        education = str(parsed_resume.get("education_experience") or "").strip()
        if not education:
            issues.append("教育经历描述不足，建议补充学校、专业、核心课程与成绩亮点。")
        if not projects:
            issues.append(f"针对 {target_role} 缺少项目证据，建议补充 1-2 个可量化项目。")
        if not internships:
            issues.append("实习经历偏少，建议补充与目标岗位相关的真实业务实践。")
        if not skills:
            issues.append("技能列表偏弱，建议补充工具栈、熟练度与典型应用场景。")
        if missing_keywords:
            issues.append(f"与目标岗位相比仍缺少关键词：{'、'.join(missing_keywords[:5])}。")
        if quantifiable_points <= 0:
            issues.append("成果量化不足，建议每段项目/实习补充 1 个可度量结果（如效率提升、转化增长、缺陷下降）。")
        return issues

    def rewrite_project(self, project: dict[str, Any], *, target_role: str, jd_keywords: list[str]) -> dict[str, Any]:
        name = str(project.get("name") or "项目经历").strip()
        role = str(project.get("role") or "核心成员").strip()
        technologies = self._to_string_list(project.get("technologies"))
        outcome = str(project.get("outcome") or "").strip()
        description = str(project.get("description") or "").strip()
        duration = self._build_duration(project.get("start_date"), project.get("end_date"))
        keyword_hint = self._keyword_hint(technologies, jd_keywords)

        result_text = outcome or description or "形成可复用的业务成果。"
        optimization_notes: list[str] = []
        if not self._has_quantification(result_text):
            optimization_notes.append("建议补充量化结果")

        keyword_clause = f"，运用 {keyword_hint} 等技术" if keyword_hint else ""
        star_text = (
            f"在 {name} 中担任 {role}，围绕 {target_role} 的核心要求{keyword_clause}，"
            f"负责关键模块设计与推进，输出结果：{result_text}"
        )
        return {
            "name": name,
            "role": role,
            "duration": duration,
            "technologies": technologies,
            "rewrite": star_text,
            "optimization_notes": optimization_notes,
        }

    def rewrite_internship(self, internship: dict[str, Any], *, target_role: str, jd_keywords: list[str]) -> dict[str, Any]:
        company = str(internship.get("company") or "实习单位").strip()
        position = str(internship.get("position") or "实习岗位").strip()
        skills = self._to_string_list(internship.get("skills"))
        description = str(internship.get("description") or "").strip()
        duration = self._build_duration(internship.get("start_date"), internship.get("end_date"))
        keyword_hint = self._keyword_hint(skills, jd_keywords)

        result_text = description or "参与岗位相关工作并沉淀可复用经验。"
        optimization_notes: list[str] = []
        if not self._has_quantification(result_text):
            optimization_notes.append("建议补充量化结果")

        keyword_clause = f"，运用 {keyword_hint} 等技能" if keyword_hint else ""
        star_text = (
            f"在 {company} 任 {position}，面向 {target_role} 开展实践{keyword_clause}，"
            f"通过跨团队协作推进任务闭环，产出：{result_text}"
        )
        return {
            "company": company,
            "position": position,
            "duration": duration,
            "skills": skills,
            "rewrite": star_text,
            "optimization_notes": optimization_notes,
        }

    @staticmethod
    def _to_string_list(value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, str):
            value = re.split(r"[,\n，、;/]+", value)
        rows: list[str] = []
        for item in value:
            text = str(item or "").strip()
            if text:
                rows.append(text)
        return rows

    def _extract_jd_tokens(self, text: str) -> list[str]:
        content = str(text or "").strip()
        if not content:
            return []
        chunks = re.split(r"[，。；；、,\n/| ]+", content)
        rows: list[str] = []
        for chunk in chunks:
            part = str(chunk).strip()
            if 2 <= len(part) <= 16:
                rows.append(part)
        return rows[:20]

    def _normalize_projects(self, value: Any) -> list[dict[str, Any]]:
        items = value if isinstance(value, list) else [value] if value else []
        rows: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            rows.append(
                {
                    "name": name,
                    "role": str(item.get("role") or "").strip(),
                    "description": str(item.get("description") or "").strip(),
                    "technologies": self._to_string_list(item.get("technologies")),
                    "outcome": str(item.get("outcome") or "").strip(),
                    "start_date": str(item.get("start_date") or "").strip(),
                    "end_date": str(item.get("end_date") or "").strip(),
                    "relevance_score": float(item.get("relevance_score") or 75),
                }
            )
        return rows[:8]

    def _normalize_internships(self, value: Any) -> list[dict[str, Any]]:
        items = value if isinstance(value, list) else [value] if value else []
        rows: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            company = str(item.get("company") or "").strip()
            position = str(item.get("position") or "").strip()
            if not company and not position:
                continue
            rows.append(
                {
                    "company": company or "实习单位",
                    "position": position or "实习岗位",
                    "description": str(item.get("description") or "").strip(),
                    "skills": self._to_string_list(item.get("skills")),
                    "start_date": str(item.get("start_date") or "").strip(),
                    "end_date": str(item.get("end_date") or "").strip(),
                    "relevance_score": float(item.get("relevance_score") or 75),
                }
            )
        return rows[:8]

    def _keyword_coverage(
        self,
        *,
        keywords: list[str],
        parsed_resume: dict[str, Any],
        skills: list[str],
        projects: list[dict[str, Any]],
        internships: list[dict[str, Any]],
    ) -> tuple[int, list[str]]:
        full_text_parts = [
            str(parsed_resume.get("summary") or ""),
            str(parsed_resume.get("bio") or ""),
            str(parsed_resume.get("education_experience") or ""),
            " ".join(skills),
        ]
        for project in projects:
            full_text_parts.extend(
                [
                    str(project.get("name") or ""),
                    str(project.get("role") or ""),
                    str(project.get("description") or ""),
                    str(project.get("outcome") or ""),
                    " ".join(self._to_string_list(project.get("technologies"))),
                ]
            )
        for internship in internships:
            full_text_parts.extend(
                [
                    str(internship.get("company") or ""),
                    str(internship.get("position") or ""),
                    str(internship.get("description") or ""),
                    " ".join(self._to_string_list(internship.get("skills"))),
                ]
            )
        full_text = " ".join(full_text_parts).lower()

        hits = 0
        missing: list[str] = []
        for keyword in keywords:
            key = str(keyword or "").strip().lower()
            if not key:
                continue
            if key in full_text:
                hits += 1
            else:
                missing.append(keyword)
        return hits, missing

    def _content_richness_score(
        self,
        parsed_resume: dict[str, Any],
        projects: list[dict[str, Any]],
        internships: list[dict[str, Any]],
        skills: list[str],
        certificates: list[str],
    ) -> float:
        points = 0
        if str(parsed_resume.get("summary") or parsed_resume.get("bio") or "").strip():
            points += 22
        if str(parsed_resume.get("education_experience") or "").strip():
            points += 18
        points += min(25, len(projects) * 8)
        points += min(20, len(internships) * 8)
        points += min(10, len(skills) * 1.2)
        points += min(5, len(certificates) * 1.2)
        return round(min(points, 100), 1)

    def _evidence_score(self, projects: list[dict[str, Any]], internships: list[dict[str, Any]]) -> tuple[float, int]:
        quantifiable_points = 0
        action_points = 0
        for item in projects:
            text = f"{item.get('description') or ''} {item.get('outcome') or ''}"
            if self._has_quantification(text):
                quantifiable_points += 1
            if self._has_action_verbs(text):
                action_points += 1
        for item in internships:
            text = str(item.get("description") or "")
            if self._has_quantification(text):
                quantifiable_points += 1
            if self._has_action_verbs(text):
                action_points += 1

        score = min(100.0, 45 + len(projects) * 10 + len(internships) * 8 + quantifiable_points * 6 + action_points * 4)
        return round(score, 1), quantifiable_points

    def _role_alignment_score(
        self,
        target_role: str,
        keywords: list[str],
        skills: list[str],
        projects: list[dict[str, Any]],
        internships: list[dict[str, Any]],
        target_job: Any | None,
    ) -> float:
        normalized_skills = {x.lower() for x in self._to_string_list(skills)}
        keyword_hits = sum(1 for key in keywords if str(key).strip().lower() in normalized_skills)
        coverage = keyword_hits / max(len(keywords), 1)

        relevance_scores: list[float] = []
        relevance_scores.extend(float(item.get("relevance_score") or 75) for item in projects)
        relevance_scores.extend(float(item.get("relevance_score") or 75) for item in internships)
        relevance_avg = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 70

        job_bonus = 5 if target_job is not None else 0
        role_bonus = 5 if str(target_role or "").strip() else 0
        score = 45 + coverage * 35 + (relevance_avg * 0.2) + job_bonus + role_bonus
        return round(min(score, 100), 1)

    def _expression_quality_score(self, parsed_resume: dict[str, Any], projects: list[dict[str, Any]], internships: list[dict[str, Any]]) -> float:
        summary = str(parsed_resume.get("summary") or parsed_resume.get("bio") or "").strip()
        summary_len = len(summary)
        if summary_len <= 0:
            summary_score = 30
        elif 50 <= summary_len <= 220:
            summary_score = 95
        else:
            summary_score = max(45, 95 - abs(summary_len - 130) * 0.35)

        star_points = 0
        entries = 0
        for item in projects:
            entries += 1
            text = f"{item.get('description') or ''} {item.get('outcome') or ''}"
            if self._has_action_verbs(text):
                star_points += 1
            if self._has_quantification(text):
                star_points += 1
        for item in internships:
            entries += 1
            text = str(item.get("description") or "")
            if self._has_action_verbs(text):
                star_points += 1
            if self._has_quantification(text):
                star_points += 1
        detail_score = (star_points / max(entries * 2, 1)) * 100
        score = summary_score * 0.55 + detail_score * 0.45
        return round(min(score, 100), 1)

    def _confidence_score(
        self,
        *,
        parsed_resume: dict[str, Any],
        projects: list[dict[str, Any]],
        internships: list[dict[str, Any]],
        jd_keywords: list[str],
        target_job: Any | None,
    ) -> float:
        raw_text_len = int(parsed_resume.get("raw_text_length") or 0)
        parser_ok = bool(parsed_resume.get("parser_success", True))

        score = 45.0
        if parser_ok:
            score += 15
        score += min(15, raw_text_len / 500)
        score += min(12, (len(projects) + len(internships)) * 3)
        score += 8 if jd_keywords else 0
        score += 5 if target_job is not None else 0
        return round(min(score, 100), 1)

    def _rewrite_summary(
        self,
        *,
        original_summary: str,
        target_role: str,
        skills: list[str],
        keyword_hit_count: int,
        keyword_total: int,
    ) -> str:
        top_skills = "、".join(skills[:4]) or "核心能力"
        if original_summary:
            summary = original_summary
            if not summary.endswith("。"):
                summary = f"{summary}。"
            return f"{summary}聚焦 {target_role} 方向，具备 {top_skills} 等与岗位强相关能力。"
        return f"围绕 {target_role} 方向，具备 {top_skills} 等核心能力，突出项目实践与量化成果。"

    def _keyword_hint(self, tags: list[str], jd_keywords: list[str]) -> str:
        tag_set = {x.lower() for x in self._to_string_list(tags)}
        matched = [k for k in jd_keywords if str(k).strip().lower() in tag_set]
        return "、".join(matched[:3])

    def _has_action_verbs(self, text: str) -> bool:
        content = str(text or "")
        return any(verb in content for verb in self._action_verbs)

    def _has_quantification(self, text: str) -> bool:
        content = str(text or "")
        if self._quant_pattern.search(content):
            return True
        return any(token in content for token in ("提升", "增长", "下降", "降低", "转化", "留存", "ROI", "DAU", "MAU", "GMV"))

    @staticmethod
    def _build_duration(start_date: Any, end_date: Any) -> str:
        start = str(start_date or "").strip()
        end = str(end_date or "").strip()
        if start and end:
            return f"{start} - {end}"
        return start or end
