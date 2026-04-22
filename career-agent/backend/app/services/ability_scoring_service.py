from statistics import mean

from app.models.student import Student


DIMENSION_LABELS = {
    "professional_skill": "专业技能",
    "certificate": "证书要求",
    "innovation": "创新能力",
    "learning": "学习能力",
    "stress_resistance": "抗压能力",
    "communication": "沟通能力",
    "internship": "实习能力",
}


class AbilityScoringService:
    def calculate(self, student: Student) -> dict:
        skill_names = [item.name for item in student.skills if not item.deleted]
        certificate_names = [item.name for item in student.certificates if not item.deleted]
        projects = [item for item in student.projects if not item.deleted]
        internships = [item for item in student.internships if not item.deleted]
        competitions = [item for item in student.competitions if not item.deleted]
        campus_experiences = [item for item in student.campus_experiences if not item.deleted]
        growth_records = [item for item in student.growth_records if not item.deleted]

        project_count = len(projects)
        internship_count = len(internships)
        competition_count = len(competitions)
        campus_count = len(campus_experiences)
        growth_count = len(growth_records)
        avg_completion = mean([item.completion_rate for item in growth_records]) if growth_records else 0

        completeness_fields = [
            student.name,
            student.student_no,
            student.major,
            student.college,
            student.phone,
            student.email,
            student.target_industry,
            student.target_city,
            student.education_experience,
            student.bio,
        ]
        filled_profile_fields = sum(1 for value in completeness_fields if str(value or "").strip())
        evidence_fields = sum(
            [
                1 if skill_names else 0,
                1 if certificate_names else 0,
                1 if projects else 0,
                1 if internships else 0,
                1 if competitions else 0,
                1 if campus_experiences else 0,
            ]
        )
        completeness_score = round(((filled_profile_fields / len(completeness_fields)) * 70 + evidence_fields / 6 * 30), 1)

        project_tech_count = sum(len(item.technologies or []) for item in projects)
        internship_skill_count = sum(len(item.skills or []) for item in internships)
        innovation_project_bonus = sum(
            1
            for item in projects
            if any(keyword in f"{item.name} {item.description or ''}".lower() for keyword in ["创新", "ai", "优化", "研究"])
        )
        teamwork_bonus = sum(
            1
            for item in projects
            if any(keyword in f"{item.role or ''} {item.description or ''}".lower() for keyword in ["团队", "组长", "负责人", "协作"])
        )

        dimension_scores = {
            "professional_skill": min(100, 38 + len(skill_names) * 8 + project_tech_count * 1.5 + project_count * 4),
            "certificate": min(100, 32 + len(certificate_names) * 18 + growth_count * 4),
            "innovation": min(100, 35 + competition_count * 14 + innovation_project_bonus * 10 + project_count * 4),
            "learning": min(100, 36 + growth_count * 8 + len(certificate_names) * 6 + avg_completion * 0.2),
            "stress_resistance": min(100, 34 + internship_count * 16 + teamwork_bonus * 8 + avg_completion * 0.22),
            "communication": min(100, 36 + campus_count * 14 + teamwork_bonus * 10 + internship_count * 6),
            "internship": min(100, 28 + internship_count * 24 + internship_skill_count * 2 + project_count * 6),
        }
        dimension_scores = {key: round(value, 1) for key, value in dimension_scores.items()}

        competitiveness_score = round(
            dimension_scores["professional_skill"] * 0.24
            + dimension_scores["certificate"] * 0.1
            + dimension_scores["innovation"] * 0.14
            + dimension_scores["learning"] * 0.14
            + dimension_scores["stress_resistance"] * 0.12
            + dimension_scores["communication"] * 0.12
            + dimension_scores["internship"] * 0.14,
            1,
        )

        ability_tags = [DIMENSION_LABELS[key] for key, score in dimension_scores.items() if score >= 75]
        strengths = [key for key, score in dimension_scores.items() if score >= 78]
        weaknesses = [key for key, score in dimension_scores.items() if score < 65]

        maturity_level = (
            "高成熟冲刺型"
            if competitiveness_score >= 85
            else "稳定成长型"
            if competitiveness_score >= 72
            else "基础提升型"
            if competitiveness_score >= 58
            else "起步积累型"
        )

        summary = (
            f"当前就业画像完整度为 {completeness_score} 分，竞争力为 {competitiveness_score} 分。"
            f"在 {', '.join(ability_tags[:3]) or '基础能力积累'} 方面表现更突出，"
            f"建议优先补齐 {', '.join(DIMENSION_LABELS[item] for item in weaknesses[:3]) or '关键岗位证据'}。"
        )

        dimension_items = [
            {
                "key": key,
                "label": DIMENSION_LABELS[key],
                "score": score,
                "description": self._build_dimension_description(key, score),
            }
            for key, score in dimension_scores.items()
        ]

        return {
            "professional_score": dimension_scores["professional_skill"],
            "practice_score": dimension_scores["internship"],
            "communication_score": dimension_scores["communication"],
            "learning_score": dimension_scores["learning"],
            "innovation_score": dimension_scores["innovation"],
            "professionalism_score": dimension_scores["stress_resistance"],
            "ability_tags": ability_tags,
            "strengths": strengths or ["learning"],
            "weaknesses": weaknesses or ["certificate"],
            "maturity_level": maturity_level,
            "summary": summary,
            "raw_metrics": {
                "skill_count": len(skill_names),
                "certificate_count": len(certificate_names),
                "project_count": project_count,
                "internship_count": internship_count,
                "competition_count": competition_count,
                "campus_count": campus_count,
                "growth_count": growth_count,
                "avg_completion": round(avg_completion, 1),
                "certificate_score": dimension_scores["certificate"],
                "stress_score": dimension_scores["stress_resistance"],
                "completeness_score": completeness_score,
                "competitiveness_score": competitiveness_score,
                "dimension_scores": dimension_items,
            },
        }

    @staticmethod
    def _build_dimension_description(key: str, score: float) -> str:
        base = {
            "professional_skill": "围绕岗位核心技能的掌握和项目应用能力。",
            "certificate": "围绕岗位要求准备证书、证明材料和规范化成果的情况。",
            "innovation": "把问题转成方案、作品或改进成果的能力。",
            "learning": "持续学习、记录复盘和快速吸收新知识的能力。",
            "stress_resistance": "面对多任务、截止时间和协作压力时保持稳定输出的能力。",
            "communication": "清晰表达、协作推进和对接反馈的能力。",
            "internship": "真实项目、实习和校企任务中的落地能力。",
        }[key]
        if score >= 80:
            return f"{base} 当前已具备较强竞争力。"
        if score >= 65:
            return f"{base} 当前处于可提升阶段。"
        return f"{base} 当前仍需优先补强。"
