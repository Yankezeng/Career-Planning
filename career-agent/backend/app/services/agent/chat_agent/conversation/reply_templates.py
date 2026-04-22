from __future__ import annotations
import random
from typing import Any


SCENE_TEMPLATES = {
    "greeting": [
        "你好！有什么职业规划方面的问题可以问我？",
        "嗨！很高兴为你服务。有什么关于职业发展的问题吗？",
        "你好呀！我是你的职业规划助手，有问题尽管问我～",
        "Hi！有什么职业方向或发展的问题吗？",
        "你好！想聊一聊职业规划吗？",
        "Hey，欢迎！有什么我能帮你的吗？",
    ],
    "confirmation": [
        "好的，你是想了解{entity}，对吗？",
        "明白了，你对{entity}感兴趣，是这样吗？",
        "我理解你想了解{entity}，没错吧？",
        "好的，我听到你想了解{entity}，对吗？",
        "了解了，你的目标是{entity}，我说得对吗？",
    ],
    "guidance": [
        "要给你更精准的分析，可以告诉我：1）你现在是学生还是职场人？2）有没有特别感兴趣的行业？",
        "了解！方便的话，可以说说你的背景：是在校生还是已经工作了？这样我能给你更合适的建议。",
        "好的！为了给你更有针对性的建议，方便透露一下你的情况吗？比如专业或工作经历～",
        "要帮你分析得更准一些，可以告诉我你目前的身份（学生/在职）和大致背景。",
        "明白！告诉我一些你的基本信息（学生还是在职，专业或行业），我能给你更精准的方向。",
    ],
    "question": [
        "让我想想...你具体想了解哪方面呢？",
        "你有什么特别想知道的吗？",
        "你想先从哪个方向开始了解？",
        "有什么具体想问我的是吗？",
    ],
    "apology": [
        "抱歉，我没能完全理解你的意思，能再说一遍吗？",
        "不好意思，可以换一种方式表达你的问题吗？",
        "抱歉，我有点困惑，你可以详细说一下你的问题吗？",
        "我不太确定你的意思，方便解释一下吗？",
    ],
    "closing": [
        "好的，有其他问题随时问我！",
        "没问题，祝你职业发展顺利！有问题再找我～",
        "有需要随时来问，祝顺利！",
        "好的，希望我的回答对你有帮助，下次见！",
        "有问题欢迎继续咨询，祝你一切顺利！",
    ],
    "partial_understanding": [
        "我理解你的意思，不过为了更好地帮助你，能多说一些吗？",
        "我听到了你的想法，但需要更多背景信息才能给你准确的分析。",
        "了解了一部分，你能再告诉我一些你的情况吗？比如学习背景或工作经验～",
    ],
    "career_confirmed": [
        "明白了，你目标是{entity}。想了解一下：你目前是学生还是已经工作过？这样我可以给你更精准的建议。",
        "好的，你的目标是{entity}。方便说一下你的背景吗？这样我能帮你分析得更准确。",
        "了解，你是想往{entity}方向发展。请问你现在是学生还是已经工作了？",
        "好的，{entity}是个不错的选择。你目前处于什么阶段呢？这样我可以给你更具体的建议。",
    ],
    "career_exploration": [
        "好的，你对{entity}感兴趣。想了解一下：你为什么对这个方向感兴趣呢？是因为专业背景还是个人爱好？",
        "了解，{entity}是很有发展的方向。你目前有什么相关的基础或经验吗？",
        "好的，你想知道成为{entity}需要什么。我可以帮你分析一下这个方向的要求和你的差距。",
    ],
    "gap_analysis": [
        "好的，我们来看看你和{entity}之间还差什么。首先需要了解你目前的背景。",
        "了解，让我们来做一个差距分析。你可以告诉我你现在的情况吗？",
        "好的，我来帮你分析一下差距。你目前是学生还是在职？有什么相关经验吗？",
    ],
    "encouragement": [
        "有目标就是好的开始！让我们一步步来。",
        "很好的方向选择！让我们来看看怎么实现它。",
        "有明确的目标很好！我来帮你规划和实现。",
        "挺好的，你有清晰的职业意识。让我们来制定一个计划吧。",
    ],
}


class ReplyTemplateLibrary:
    @staticmethod
    def get_template(scene: str, index: int | None = None) -> str:
        templates = SCENE_TEMPLATES.get(scene, SCENE_TEMPLATES["question"])
        if index is not None and 0 <= index < len(templates):
            return templates[index]
        return templates[0]

    @staticmethod
    def get_random_template(scene: str) -> str:
        templates = SCENE_TEMPLATES.get(scene, SCENE_TEMPLATES["question"])
        return random.choice(templates)

    @staticmethod
    def format_template(scene: str, **kwargs) -> str:
        template = ReplyTemplateLibrary.get_random_template(scene)
        try:
            return template.format(**kwargs)
        except KeyError:
            return template

    @staticmethod
    def get_all_scenes() -> list[str]:
        return list(SCENE_TEMPLATES.keys())


def get_reply_template_library() -> ReplyTemplateLibrary:
    return ReplyTemplateLibrary()