from __future__ import annotations

import re
from typing import Any

from app.services.assistant_skill_catalog_service import normalize_skill_code


_JOB_TEXT_PATTERN = r"[\u4e00-\u9fa5A-Za-z0-9+#.]{2,30}"

_GROWTH_TOKENS = (
    "growth",
    "roadmap",
    "path",
    "\u6210\u957f",
    "\u6210\u957f\u8def\u5f84",
    "\u6210\u957f\u8def\u7ebf",
    "\u5b66\u4e60\u8def\u7ebf",
    "\u5b66\u4e60\u8ba1\u5212",
    "\u8def\u5f84",
    "\u8def\u7ebf",
    "\u89c4\u5212",
    "\u8ba1\u5212",
    "\u804c\u4e1a\u8def\u5f84",
)

_GAP_TOKENS = (
    "gap",
    "\u5dee\u8ddd",
    "\u7f3a\u4ec0\u4e48",
    "\u77ed\u677f",
    "\u4e0d\u8db3",
    "\u8865\u9f50",
)

_MATCH_TOKENS = (
    "match",
    "job",
    "\u63a8\u8350\u804c\u4e1a",
    "\u63a8\u8350\u5c97\u4f4d",
    "\u76ee\u6807\u5c97\u4f4d",
    "\u76ee\u6807\u804c\u4e1a",
    "\u804c\u4e1a",
    "\u5c97\u4f4d",
    "\u804c\u4f4d",
    "\u5339\u914d",
    "\u9002\u5408",
)

_JOB_ANCHORS = (
    "targetjob",
    "targetcareer",
    "\u63a8\u8350\u804c\u4e1a",
    "\u76ee\u6807\u5c97\u4f4d",
    "\u76ee\u6807\u804c\u4e1a",
    "\u804c\u4e1a\u662f",
    "\u5c97\u4f4d\u662f",
    "\u804c\u4f4d\u662f",
    "\u804c\u4e1a\u65b9\u5411",
)

_CONTINUE_TOKENS = (
    "\u7ee7\u7eed",
    "\u63a5\u7740",
    "\u5c55\u5f00",
    "\u7ec6\u8bf4",
    "\u521a\u624d",
    "\u4e0a\u4e00\u8f6e",
    "\u4e0a\u6b21",
    "\u4ecd\u7136",
    "\u4fdd\u6301",
    "\u518d\u770b",
    "\u518d\u5206\u6790",
)

_PROFILE_IMAGE_SKILLS = {"profile-image"}

_JOB_ALIASES = (
    ("Java\u5f00\u53d1\u5de5\u7a0b\u5e08", ("java\u5f00\u53d1\u5de5\u7a0b\u5e08", "java\u5de5\u7a0b\u5e08", "java\u5f00\u53d1")),
    ("\u524d\u7aef\u5f00\u53d1\u5de5\u7a0b\u5e08", ("\u524d\u7aef\u5f00\u53d1\u5de5\u7a0b\u5e08", "\u524d\u7aef\u5de5\u7a0b\u5e08", "\u524d\u7aef\u5f00\u53d1")),
    ("\u540e\u7aef\u5f00\u53d1\u5de5\u7a0b\u5e08", ("\u540e\u7aef\u5f00\u53d1\u5de5\u7a0b\u5e08", "\u540e\u7aef\u5de5\u7a0b\u5e08", "\u540e\u7aef\u5f00\u53d1")),
    ("Python\u5f00\u53d1\u5de5\u7a0b\u5e08", ("python\u5f00\u53d1\u5de5\u7a0b\u5e08", "python\u5de5\u7a0b\u5e08", "python\u5f00\u53d1")),
    ("\u4ea7\u54c1\u7ecf\u7406", ("\u4ea7\u54c1\u7ecf\u7406", "\u4ea7\u54c1\u52a9\u7406", "\u4ea7\u54c1\u7b56\u5212")),
    ("\u6570\u636e\u5206\u6790\u5e08", ("\u6570\u636e\u5206\u6790\u5e08", "\u6570\u636e\u5206\u6790")),
    ("\u7b97\u6cd5\u5de5\u7a0b\u5e08", ("\u7b97\u6cd5\u5de5\u7a0b\u5e08", "\u7b97\u6cd5")),
    ("\u6d4b\u8bd5\u5de5\u7a0b\u5e08", ("\u6d4b\u8bd5\u5de5\u7a0b\u5e08", "\u6d4b\u8bd5")),
)


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "").strip())


def has_explicit_continue_request(text: str) -> bool:
    compact = compact_text(text).lower()
    return any(token in compact for token in _CONTINUE_TOKENS)


def is_profile_image_skill(skill: str | None) -> bool:
    return normalize_skill_code(skill or "") in _PROFILE_IMAGE_SKILLS


def extract_target_job_from_text(text: str) -> str:
    compact = compact_text(text)
    if not compact:
        return ""

    lowered = compact.lower()
    for canonical, aliases in _JOB_ALIASES:
        if any(alias in lowered for alias in aliases):
            return canonical
    if any(token in compact for token in ("\u753b\u50cf\u56fe", "\u753b\u50cf\u56fe\u7247", "\u751f\u6210\u56fe\u7247", "\u521b\u5efa\u56fe\u7247", "\u6d77\u62a5", "\u5934\u50cf")):
        return ""

    patterns = (
        rf"(?:\u63a8\u8350\u804c\u4e1a|\u76ee\u6807\u5c97\u4f4d|\u76ee\u6807\u804c\u4e1a|\u804c\u4e1a\u65b9\u5411|\u804c\u4e1a|\u5c97\u4f4d|\u804c\u4f4d)(?:\u662f|\u4e3a|=|:|\uff1a)?({_JOB_TEXT_PATTERN}?)(?:\uff0c|,|\u3002|\.|;|\uff1b|\u8bf7|\u5e2e|\u4e3a\u6211|\u7ed9\u6211|\u89c4\u5212|\u5236\u5b9a|\u751f\u6210|\u8f93\u51fa|$)",
        rf"(?:\u6309|\u4ee5|\u56f4\u7ed5|\u9488\u5bf9)({_JOB_TEXT_PATTERN}?)(?:\u89c4\u5212|\u5236\u5b9a|\u751f\u6210|\u505a|\u5206\u6790|\u6210\u957f|\u5b66\u4e60|\u8def\u5f84|\u8def\u7ebf)",
        rf"(?:\u60f3\u505a|\u60f3\u6210\u4e3a|\u51c6\u5907\u505a|\u5e0c\u671b\u505a)({_JOB_TEXT_PATTERN}?)(?:\uff0c|,|\u3002|\.|;|\uff1b|\u8bf7|\u5e2e|\u4e3a\u6211|\u7ed9\u6211|\u89c4\u5212|\u5236\u5b9a|\u751f\u6210|\u8f93\u51fa|$)",
        rf"(?:\u89c4\u5212|\u5236\u5b9a|\u751f\u6210)(?:\u4e00\u4e2a)?({_JOB_TEXT_PATTERN}?)(?:\u7684)?(?:\u6210\u957f|\u5b66\u4e60|\u8def\u5f84|\u8def\u7ebf|\u8ba1\u5212)",
    )
    for pattern in patterns:
        matches = re.findall(pattern, compact, flags=re.IGNORECASE)
        for candidate in reversed(matches):
            normalized = _normalize_job(candidate)
            if normalized:
                return normalized
    return ""


def has_explicit_growth_planning_intent(
    text: str,
    *,
    slots: dict[str, Any] | None = None,
    intent_info: dict[str, Any] | None = None,
) -> bool:
    compact = compact_text(text).lower()
    if not any(token in compact for token in _GROWTH_TOKENS):
        return False
    if _target_job_from_context(text=text, slots=slots, intent_info=intent_info):
        return True
    return any(anchor in compact for anchor in _JOB_ANCHORS)


def infer_explicit_student_skill(
    text: str,
    *,
    slots: dict[str, Any] | None = None,
    intent_info: dict[str, Any] | None = None,
) -> str:
    if has_explicit_growth_planning_intent(text, slots=slots, intent_info=intent_info):
        return "growth-planner"

    compact = compact_text(text).lower()
    if not _target_job_from_context(text=text, slots=slots, intent_info=intent_info):
        return ""
    if any(token in compact for token in _GAP_TOKENS):
        return "gap-analysis"
    if any(token in compact for token in _MATCH_TOKENS):
        return "match-center"
    return ""


def should_ignore_stale_profile_skill(*, selected_skill: str | None, text: str) -> bool:
    if not is_profile_image_skill(selected_skill):
        return False
    compact = compact_text(text).lower()
    if any(token in compact for token in ("image", "poster", "cbti", "mbti")):
        return False
    return bool(infer_explicit_student_skill(text, slots={"target_job": extract_target_job_from_text(text)}))


def _target_job_from_context(
    *,
    text: str,
    slots: dict[str, Any] | None,
    intent_info: dict[str, Any] | None,
) -> str:
    slots = slots or {}
    intent_info = intent_info or {}
    return str(slots.get("target_job") or intent_info.get("extracted_job") or extract_target_job_from_text(text) or "").strip()


def _normalize_job(value: str) -> str:
    text = str(value or "").strip(" \t\r\n,，。.;；:：")
    if not text:
        return ""
    lowered = text.lower()
    for canonical, aliases in _JOB_ALIASES:
        if any(alias == lowered or alias in lowered for alias in aliases):
            return canonical
    return text
