from __future__ import annotations


PROFILE_IMAGE_TOKENS = (
    "画像图",
    "职业画像图",
    "人物画像图",
    "画像图片",
    "生成图片",
    "创建图片",
    "做图",
    "配图",
    "海报",
    "头像",
    "形象照",
    "视觉画像",
    "可视化画像",
    "image",
    "poster",
    "visualprofile",
    "cbti",
    "mbti",
    "\u4eba\u7269\u753b\u50cf",
    "\u4e2a\u4eba\u753b\u50cf",
)

PROFILE_INSIGHT_TOKENS = (
    "人物画像",
    "个人画像",
    "职业画像",
    "简历画像",
    "能力画像",
    "人才画像",
    "学生画像",
    "候选人画像",
    "画像报告",
    "画像表格",
    "人格分析",
    "性格分析",
    "能力分析",
    "优势",
    "短板",
    "profile",
)


def _compact(text: str) -> str:
    return "".join(str(text or "").lower().split())


def is_profile_image_intent(text: str) -> bool:
    compact = _compact(text)
    return any(token in compact for token in PROFILE_IMAGE_TOKENS)


def is_profile_insight_intent(text: str) -> bool:
    compact = _compact(text)
    return any(token in compact for token in PROFILE_INSIGHT_TOKENS) and not is_profile_image_intent(compact)
