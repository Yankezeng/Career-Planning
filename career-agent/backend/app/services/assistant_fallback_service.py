from __future__ import annotations

import re
from typing import Any


_GENERIC_ERROR_HINT = "这次复杂问题的深度分析没有完整完成，我先给你一个稳妥可执行的建议。"
_INTERNAL_ERROR_TOKENS = (
    "traceback",
    "exception",
    "stack",
    "agent",
    "supervisor",
    "dispatch",
    "workflow",
    "timeout",
    "timed out",
    "runtimeerror",
    "valueerror",
    "keyerror",
    "importerror",
    "modulenotfounderror",
    "no module named",
    "llm",
    "ssl",
    "network error",
    "unexpected_eof",
    "unexpected eof",
    "eof occurred",
    "provider",
    "urlerror",
    "connection",
    "connectionreset",
    "remote disconnected",
    "remote end closed",
    "api key",
    "not configured",
)


def sanitize_student_visible_error(raw_message: str | None, *, default: str = _GENERIC_ERROR_HINT) -> str:
    text = str(raw_message or "").strip()
    if not text:
        return default
    lowered = text.lower()
    if any(token in lowered for token in _INTERNAL_ERROR_TOKENS):
        return default
    if len(text) > 160:
        return default
    return text


def _first_context_value(field: str, *sources: Any) -> str:
    for source in sources:
        if not isinstance(source, dict):
            continue
        value = source.get(field)
        if value not in (None, "", 0, "0", "none", "null"):
            return str(value).strip()
        nested = source.get("context_binding") if isinstance(source.get("context_binding"), dict) else {}
        value = nested.get(field)
        if value not in (None, "", 0, "0", "none", "null"):
            return str(value).strip()
    return ""


def _clean_target_job(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^[：:\s,，。;；、]+|[：:\s,，。;；、]+$", "", text)
    text = re.sub(r"(请你|请帮我|帮我|为我|给我|规划|分析|做|一个|一下).*$", "", text).strip()
    return text[:30]


def _infer_target_job_from_message(message: str) -> str:
    text = str(message or "").strip()
    if not text:
        return ""
    patterns = [
        r"(?:推荐职业|推荐岗位|目标岗位|目标职位|求职方向|发展方向)\s*(?:是|为|:|：)?\s*([^，。,；;、\n]{2,40})",
        r"(?:围绕|面向|朝)\s*([^，。,；;、\n]{2,40}?)(?:方向|岗位|职位)",
        r"([^，。,；;、\n]{2,30}?(?:开发工程师|工程师|设计师|分析师|产品经理|运营|测试|算法|前端|后端|Java|Python))",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = _clean_target_job(match.group(1))
            if value:
                if value.lower() == "java":
                    return "Java 开发工程师"
                return value
    if "java" in text.lower():
        return "Java 开发工程师"
    return ""


def _fallback_kind(*, message: str, selected_skill: str) -> str:
    compact = str(message or "").lower().replace(" ", "")
    skill = str(selected_skill or "").strip().lower().replace("_", "-")
    if skill == "gap-analysis" or any(token in compact for token in ("能力差距", "差距", "短板", "最该补", "补什么", "能力")):
        return "gap"
    if skill == "growth-planner" or any(token in compact for token in ("成长路径", "成长计划", "行动计划", "下一步", "规划", "路线")):
        return "plan"
    if skill == "resume-workbench" or any(token in compact for token in ("简历", "投递材料", "履历")):
        return "resume"
    if skill == "match-center" or any(token in compact for token in ("推荐职业", "推荐岗位", "岗位匹配", "人岗匹配")):
        return "match"
    return "general"


def _build_gap_reply(target_job: str) -> tuple[str, list[str], str]:
    conclusion = f"能力差距分析：先把 {target_job} 拆成技术栈、项目证据、表达呈现三条线，优先补最影响投递通过率的短板。"
    suggestions = [
        f"1. 技术栈差距：对照 {target_job} 常见要求，先确认 Java 基础、数据库、Web 框架、接口开发和工程化工具是否能做成可展示案例。",
        "2. 项目经验差距：把课程项目或实习项目整理成“业务背景、负责模块、技术方案、量化结果”，至少准备 1 个主讲项目。",
        "3. 简历表达差距：把“学过/了解”改成“使用某技术完成某功能，带来某结果”，减少空泛技能堆叠。",
        "4. 面试表达差距：准备 60 秒自我介绍、项目难点复盘、异常排查案例，先保证能讲清楚自己做过什么。",
    ]
    next_step = "下一步：先把你当前简历或项目经历发我，我可以继续按岗位要求逐项标注“已具备 / 待补齐 / 优先补强”。"
    return conclusion, suggestions, next_step


def _build_plan_reply(target_job: str) -> tuple[str, list[str], str]:
    conclusion = f"成长路径：围绕 {target_job} 先定岗位优先级，再用 7 天短周期把知识点、项目证据和投递材料串起来。"
    suggestions = [
        "1. 前 2 天：梳理岗位 JD 高频要求，列出必须掌握的技术栈和当前缺口。",
        "2. 第 3 到 5 天：选择 1 个项目做深，把接口、数据库、异常处理、部署或性能优化补成可讲证据。",
        "3. 第 6 天：重写简历项目段落，突出技术动作、个人贡献和结果。",
        "4. 第 7 天：模拟 HR 自我介绍和技术追问，整理投递版本并开始小范围投递。",
    ]
    next_step = "下一步：你可以让我继续生成“7 天详细行动表”或“Java 开发工程师能力差距清单”。"
    return conclusion, suggestions, next_step


def _build_resume_reply(target_job: str) -> tuple[str, list[str], str]:
    conclusion = f"简历管理建议：简历先服务于 {target_job} 的投递，通过岗位关键词、项目证据和表达结构来提升通过率。"
    suggestions = [
        "1. 建立一份主简历和一份投递版简历，主简历保留完整经历，投递版只保留与目标岗位最相关的内容。",
        "2. 每个项目用“背景、任务、技术方案、结果”四段式表达，避免只罗列技术名词。",
        "3. 上传简历后先做识别和画像回填，再根据目标岗位生成优化版本。",
    ]
    next_step = "下一步：进入简历管理页上传当前简历，或直接把项目经历发我，我帮你改成可投递表达。"
    return conclusion, suggestions, next_step


def _build_match_reply(target_job: str) -> tuple[str, list[str], str]:
    conclusion = f"岗位匹配建议：先用 {target_job} 作为主攻方向，再对比匹配度、差距项和投递准备度。"
    suggestions = [
        "1. 先生成或刷新学生画像，确保技能、项目、实习和证书信息完整。",
        "2. 查看前三个匹配岗位，不只看分数，也要看差距项是否能在短期内补齐。",
        "3. 把最高优先级岗位同步到成长路径和简历管理，避免规划、简历、投递互相脱节。",
    ]
    next_step = "下一步：我可以继续帮你解释前三个岗位为什么匹配，或拆出最高匹配岗位的能力差距。"
    return conclusion, suggestions, next_step


def build_career_guidance_fallback(
    *,
    message: str,
    selected_skill: str = "",
    session_state: dict[str, Any] | None = None,
    context_binding: dict[str, Any] | None = None,
    client_state: dict[str, Any] | None = None,
    reason: str = "",
) -> dict[str, Any]:
    text = str(message or "").strip()
    compact = text.lower().replace(" ", "")
    session_state = session_state or {}
    context_binding = context_binding or {}
    client_state = client_state or {}

    target_job = (
        _first_context_value("target_job", client_state, context_binding, session_state)
        or _infer_target_job_from_message(text)
        or "目标岗位"
    )
    kind = _fallback_kind(message=text, selected_skill=selected_skill)
    need_intro = any(token in compact for token in ("自我介绍", "hr", "面试", "沟通", "介绍自己"))

    if kind == "gap":
        conclusion, suggestions, next_step = _build_gap_reply(target_job)
    elif kind == "plan":
        conclusion, suggestions, next_step = _build_plan_reply(target_job)
    elif kind == "resume":
        conclusion, suggestions, next_step = _build_resume_reply(target_job)
    elif kind == "match":
        conclusion, suggestions, next_step = _build_match_reply(target_job)
    else:
        conclusion = (
            f"结论：当前模型服务连接不稳定，我先基于已有信息给你一版可执行建议。建议先围绕 {target_job} 明确优先级，"
            "再把项目证据和表达话术准备到可直接使用。"
        )
        suggestions = [
            f"1. 先找 1 个最接近的 {target_job} 岗位描述，整理出 3 到 5 个高频要求，并标记已具备和待补齐的部分。",
            "2. 从课程项目、实习或竞赛里挑 1 个案例，补成“做了什么、怎么做、结果如何”的证据表达。",
            "3. 准备一版 60 秒口头表达，讲清专业背景、核心项目、正在补强的能力和求职方向。",
        ]
        next_step = "下一步：你可以继续让我只做其中一块，例如“能力差距分析”“HR 自我介绍润色”或“7 天行动计划”。"

    reply_lines = [conclusion, "", "建议：", *suggestions, "", next_step]

    if need_intro:
        script = (
            f"可直接对 HR 这样说：\n"
            f"“你好，我目前正朝 {target_job} 方向准备，已经完成了课程和项目基础训练，"
            "现在重点在补强项目证据和表达呈现。如果你愿意，我可以结合一个具体项目，"
            "用 1 分钟介绍我最适合这个岗位的能力。”"
        )
        reply_lines.extend(["", script])

    if selected_skill and selected_skill != "general-chat":
        reply_lines.extend(["", f"说明：当前已切换为稳妥回答模式，先保证你能拿到可执行建议。"])

    reply = "\n".join(reply_lines).strip()
    return {
        "reply": reply,
        "reply_blocks": [
            {"type": "summary", "text": conclusion},
            {"type": "summary", "text": next_step},
        ],
        "context_binding": {"target_job": target_job},
        "session_state": {"context_binding": {"target_job": target_job}, "current_focus": kind},
        "actions": [
            f"让我帮你拆解 {target_job} 的能力差距",
            "让我帮你润色一版 HR 自我介绍",
            "让我帮你生成 7 天行动计划",
        ],
        "error_message": _GENERIC_ERROR_HINT,
    }
