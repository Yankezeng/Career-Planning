from __future__ import annotations
import random
from typing import Any


class NLGService:
    def confirm_intent(self, user_intent: str, entity: str | None = None) -> str:
        """生成意图确认语"""
        if entity:
            templates = [
                f"好的，你是想了解{entity}，对吗？",
                f"明白了，你对{entity}感兴趣，是这样吗？",
                f"我理解你想了解{entity}，没错吧？",
            ]
        else:
            templates = [
                "好的，我理解你的意思了。",
                "明白了，让我确认一下你的需求。",
                "好的，我听到了。",
            ]
        return random.choice(templates)

    def guide_user(self, missing_info: list[str] | None = None, context: dict[str, Any] | None = None) -> str:
        """生成引导性回复"""
        missing_info = missing_info or []
        context = context or {}

        if missing_info:
            info_labels = {
                "target_job": "目标岗位",
                "target_city": "目标城市",
                "target_industry": "目标行业",
                "role": "身份（学生/在职）",
                "major": "专业背景",
            }
            labels = [info_labels.get(info, info) for info in missing_info[:2]]

            if len(labels) == 1:
                return f"了解！为了给你更精准的分析，可以告诉我你的{labels[0]}吗？"
            elif len(labels) == 2:
                return f"了解！方便告诉我你的{labels[0]}和{labels[1]}吗？这样我能给你更合适的建议。"

        default_templates = [
            "要给你更精准的分析，可以告诉我一些你的基本情况。",
            "了解！方便说说你的背景吗？比如是学生还是在工作～",
            "好的，为了给你更有针对性的建议，能多说一些你的情况吗？",
        ]
        return random.choice(default_templates)

    def express_understanding(self, user_message: str, context: dict[str, Any] | None = None) -> str:
        """生成共情回复"""
        context = context or {}
        target_job = context.get("target_job", "")

        if target_job:
            templates = [
                f"好的，你对{target_job}感兴趣，这是个很有发展的方向。",
                f"了解，{target_job}是个不错的选择。",
                f"好的，{target_job}是很有前景的方向。",
            ]
        else:
            templates = [
                "好的，了解你的想法了。",
                "明白了，让我来帮你分析一下。",
                "好的，我听到了。",
            ]
        return random.choice(templates)

    def suggest_next(self, suggestions: list[str] | None = None, context: dict[str, Any] | None = None) -> str:
        """生成建议回复"""
        suggestions = suggestions or []
        context = context or {}

        if suggestions:
            return f"你可以：{'；'.join(suggestions[:3])}"

        default_templates = [
            "有什么其他问题随时问我。",
            "有需要随时来问，祝顺利！",
            "有问题欢迎继续咨询。",
        ]
        return random.choice(default_templates)

    def acknowledge_negative(self, message: str, context: dict[str, Any] | None = None) -> str:
        """处理用户否定或模糊表达"""
        context = context or {}

        negative_patterns = ["没有目标", "不知道", "不确定", "迷茫"]
        for pattern in negative_patterns:
            if pattern in message:
                templates = [
                    "没关系的，很多人一开始都不太确定自己的方向。让我们一起来探索一下。",
                    "好的，职业规划本来就是一个探索的过程。你平时对什么类型的工作比较感兴趣呢？",
                    "了解。那我们先聊聊，你有没有什么特别想尝试的方向？哪怕不太确定也没关系。",
                    "好的，迷茫是正常的。让我们一起理清思路，找到适合你的方向。",
                ]
                return random.choice(templates)

        return "好的，我明白了。"

    def generate_greeting(self, context: dict[str, Any] | None = None) -> str:
        """生成寒暄回复"""
        context = context or {}
        last_topic = context.get("last_topic", "")

        if last_topic:
            templates = [
                f"嗨，我们之前聊到{last_topic}，想继续深入聊聊吗？",
                f"欢迎回来！之前我们在讨论{last_topic}，有什么想继续了解的吗？",
                f"你好！我们可以继续之前的话题，关于{last_topic}。",
            ]
        else:
            templates = [
                "你好！有什么职业规划方面的问题可以问我？",
                "嗨！很高兴为你服务。有什么关于职业发展的问题吗？",
                "你好呀！我是你的职业规划助手，有问题尽管问我～",
            ]
        return random.choice(templates)

    def generate_career_acknowledgment(self, target_job: str, context: dict[str, Any] | None = None) -> str:
        """生成职业目标确认回复"""
        context = context or {}

        templates = [
            f"好的，你的目标是{target_job}。想了解一下：你目前是学生还是已经工作过？这样我可以给你更精准的建议。",
            f"明白了，你想做{target_job}。方便说一下你的背景吗？这样我能帮你分析得更准确。",
            f"了解，你是想往{target_job}方向发展。请问你现在是学生还是已经工作了？",
            f"好的，{target_job}是个不错的选择。你目前处于什么阶段呢？这样我可以给你更具体的建议。",
        ]
        return random.choice(templates)

    def generate_encouragement(self, context: dict[str, Any] | None = None) -> str:
        """生成鼓励回复"""
        templates = [
            "有目标就是好的开始！让我们一步步来。",
            "很好的方向选择！让我们来看看怎么实现它。",
            "有目标很好！我来帮你规划和实现。",
            "挺好的，你有清晰的职业意识。让我们来制定一个计划吧。",
        ]
        return random.choice(templates)


_nlg_service_instance = None

def get_nlg_service() -> NLGService:
    global _nlg_service_instance
    if _nlg_service_instance is None:
        _nlg_service_instance = NLGService()
    return _nlg_service_instance