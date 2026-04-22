from __future__ import annotations

from copy import deepcopy
from typing import Any

RoleCode = str
SkillCode = str


def _skill(code: str, name: str, description: str, roles: list[str], **extra: Any) -> dict[str, Any]:
    return {
        "code": code,
        "name": name,
        "description": description,
        "roles": roles,
        "icon_key": extra.get("icon_key", "skill"),
        "default_action_type": extra.get("default_action_type", "chat"),
        "route": extra.get("route", ""),
        "recommended_prompts": extra.get("recommended_prompts", []),
        "tools": extra.get("tools", []),
    }


SKILL_CATALOG: dict[SkillCode, dict[str, Any]] = {
    "general-chat": _skill("general-chat", "General Chat", "General Q&A and follow-up conversation.", ["student", "enterprise", "admin"], icon_key="chat"),
    "code-agent": _skill(
        "code-agent",
        "Code Agent",
        "Generate code and output only after strict backend compile/syntax checks and self-tests pass.",
        ["student", "enterprise", "admin"],
        icon_key="code",
        route="/assistant",
        tools=["generate_verified_code"],
        recommended_prompts=[
            "Write Python code and include assert-based tests",
            "Generate C++ code and verify compile + smoke test",
            "Create Vue SFC and verify parser/compile checks",
        ],
    ),
    "resume-workbench": _skill("resume-workbench", "Resume Workbench", "Parse and optimize resumes.", ["student"], icon_key="resume", route="/student/resume", tools=["parse_resume_attachment", "optimize_resume"]),
    "profile-insight": _skill("profile-insight", "Profile Insight", "Generate capability profile insights.", ["student"], icon_key="profile", route="/profile/insight", tools=["ingest_resume_attachment", "generate_profile"]),
    "profile-image": _skill("profile-image", "Profile Image", "Generate student persona and visual profile image.", ["student"], icon_key="profile", route="/profile/insight", tools=["generate_profile_image"]),
    "match-center": _skill("match-center", "Match Center", "Generate job matching results.", ["student"], icon_key="match", route="/matches/center", tools=["generate_matches"]),
    "gap-analysis": _skill("gap-analysis", "Gap Analysis", "Analyze skill and requirement gaps.", ["student"], icon_key="gap", route="/matches/center?tab=gaps", tools=["generate_gap_analysis"]),
    "growth-planner": _skill("growth-planner", "Growth Planner", "Generate growth path and learning plan.", ["student"], icon_key="growth", route="/career/center", tools=["generate_growth_path"]),
    "report-builder": _skill("report-builder", "Report Builder", "Generate career planning reports.", ["student"], icon_key="report", route="/reports/center", tools=["generate_report"]),
    "delivery-ready": _skill("delivery-ready", "Delivery Ready", "Pre-delivery checklist and suggestions.", ["student"], icon_key="delivery", tools=["prepare_delivery"]),
    "interview-training": _skill("interview-training", "Interview Training", "Generate interview questions and drills.", ["student"], icon_key="interview", tools=["generate_interview_questions"]),
    "candidate-overview": _skill("candidate-overview", "Candidate Overview", "Candidate pool summary.", ["enterprise"], icon_key="candidate", route="/enterprise/deliveries", tools=["build_candidate_overview"]),
    "candidate-screening": _skill("candidate-screening", "Candidate Screening", "Candidate ranking and prioritization.", ["enterprise"], icon_key="screen", route="/enterprise/deliveries", tools=["rank_candidates"]),
    "resume-review": _skill("resume-review", "Resume Review", "Resume review and feedback for candidates.", ["enterprise"], icon_key="review", route="/enterprise/deliveries", tools=["generate_resume_review"]),
    "talent-portrait": _skill("talent-portrait", "Talent Portrait", "Talent profile summary.", ["enterprise"], icon_key="portrait", route="/enterprise/deliveries", tools=["generate_talent_portrait"]),
    "delivery-priority": _skill("delivery-priority", "Delivery Priority", "Delivery ordering and recommendation.", ["enterprise"], icon_key="priority", route="/enterprise/deliveries", tools=["rank_candidates"]),
    "interview-eval": _skill("interview-eval", "Interview Evaluation", "Interview evaluation guidance.", ["enterprise"], icon_key="interview", tools=["generate_interview_questions"]),
    "communication-script": _skill("communication-script", "Communication Script", "Generate communication scripts.", ["enterprise"], icon_key="script", tools=["build_communication_script"]),
    "review-advice": _skill("review-advice", "Review Advice", "Output review conclusions and advice.", ["enterprise"], icon_key="advice", tools=["generate_review_advice"]),
    "admin-metrics": _skill("admin-metrics", "Admin Metrics", "Administrative metrics summary.", ["admin"], icon_key="metrics", route="/dashboard", tools=["summarize_admin_metrics"]),
    "ops-review": _skill("ops-review", "Ops Review", "Operations review suggestions.", ["admin"], icon_key="ops", tools=["summarize_ops_review"]),
    "role-overview": _skill("role-overview", "Role Overview", "Cross-role ability overview.", ["admin"], icon_key="role", tools=["build_role_overview"]),
    "knowledge-governance": _skill("knowledge-governance", "Knowledge Governance", "Knowledge base governance checks.", ["admin"], icon_key="knowledge", route="/jobs", tools=["inspect_knowledge_governance"]),
    "data-governance": _skill("data-governance", "Data Governance", "Data quality and governance checks.", ["admin"], icon_key="data", route="/admin/configs", tools=["inspect_data_governance"]),
    "demo-script": _skill("demo-script", "Demo Script", "Demo and defense script generation.", ["admin"], icon_key="demo", route="/dashboard", tools=["generate_demo_script"]),
}


LEGACY_SKILL_MAP: dict[str, SkillCode] = {
    "resume_optimize": "resume-workbench",
    "ability_profile": "profile-insight",
    "job_match": "match-center",
    "career_path": "growth-planner",
    "report_generate": "report-builder",
    "candidate_screen": "candidate-screening",
    "candidate-screen": "candidate-screening",
    "review_feedback": "review-advice",
    "review-feedback": "review-advice",
    "system_monitor": "admin-metrics",
    "metrics-analysis": "admin-metrics",
    "job-recommend": "match-center",
    "job_recommend": "match-center",
    "match_center": "match-center",
    "growth_planner": "growth-planner",
    "profile_insight": "profile-insight",
    "profile_image": "profile-image",
    "profile-image": "profile-image",
    "ability_image": "profile-image",
    "persona_image": "profile-image",
    "mbti": "profile-image",
    "cbti": "profile-image",
    "persona-report": "profile-image",
    "profile-report": "profile-image",
    "report_builder": "report-builder",
    "code_agent": "code-agent",
    "code-agent": "code-agent",
    "coding": "code-agent",
}


def _normalize_token(value: str | None) -> str:
    return str(value or "").strip().lower().replace("_", "-")


def normalize_skill_code(skill_code: str | None, role: RoleCode | None = None) -> SkillCode:
    token = _normalize_token(skill_code)
    if not token:
        return "general-chat"
    mapped = LEGACY_SKILL_MAP.get(token, token)
    if mapped not in SKILL_CATALOG:
        return "general-chat"
    if role and role not in (SKILL_CATALOG[mapped].get("roles") or []):
        return "general-chat"
    return mapped


def get_skill_definition(skill_code: str | None) -> dict[str, Any]:
    code = normalize_skill_code(skill_code)
    return deepcopy(SKILL_CATALOG.get(code, SKILL_CATALOG["general-chat"]))


def list_skills_for_role(role: RoleCode) -> list[dict[str, Any]]:
    role_key = _normalize_token(role) or "student"
    rows = [deepcopy(skill) for skill in SKILL_CATALOG.values() if role_key in (skill.get("roles") or [])]
    rows.sort(key=lambda item: item["code"])
    return rows
