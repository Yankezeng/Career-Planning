from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.knowledge.job_kb_milvus import MilvusJobKnowledgeBase
from app.services.knowledge.langchain_career_agent import LangChainCareerAgent


def build_context(args: argparse.Namespace) -> dict:
    return {
        "role": args.role,
        "user_name": args.name,
        "major": args.major,
        "target_industry": args.industry,
        "target_city": args.city,
        "interests": [item.strip() for item in args.interests.split(",") if item.strip()],
        "profile_summary": args.profile_summary,
        "strengths": [item.strip() for item in args.strengths.split(",") if item.strip()],
        "weaknesses": [item.strip() for item in args.weaknesses.split(",") if item.strip()],
        "latest_path_summary": args.path_summary,
        "selected_skill": args.skill,
        "top_jobs": [{"job_name": args.target_job, "score": 82.0}] if args.target_job else [],
    }


def run_once(agent: LangChainCareerAgent, args: argparse.Namespace) -> None:
    context = build_context(args)
    reply = agent.invoke(
        user_role=args.role,
        user_name=args.name,
        message=args.query,
        history=[],
        context=context,
    )
    print("\nCareer Agent:\n")
    print(reply)


def run_interactive(agent: LangChainCareerAgent, args: argparse.Namespace) -> None:
    context = build_context(args)
    history: list[dict] = []
    print("Career Agent 已启动，输入 exit / quit 结束会话。\n")
    while True:
        message = input("你：").strip()
        if not message:
            continue
        if message.lower() in {"exit", "quit"}:
            print("会话结束。")
            return

        reply = agent.invoke(
            user_role=args.role,
            user_name=args.name,
            message=message,
            history=history,
            context=context,
        )
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": reply})
        print(f"\nCareer Agent：\n{reply}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the career planning agent in PyCharm or terminal.")
    parser.add_argument("--role", default="student", choices=["student", "enterprise", "admin"])
    parser.add_argument("--name", default="演示学生")
    parser.add_argument("--major", default="计算机科学与技术")
    parser.add_argument("--industry", default="互联网")
    parser.add_argument("--city", default="上海")
    parser.add_argument("--interests", default="数据分析,后端开发")
    parser.add_argument("--strengths", default="学习能力强,项目推进能力较好")
    parser.add_argument("--weaknesses", default="缺少实习经历,岗位关键词表达不够精准")
    parser.add_argument("--profile-summary", dest="profile_summary", default="具备基础专业能力，适合围绕目标岗位继续强化项目与实习。")
    parser.add_argument("--path-summary", dest="path_summary", default="建议未来 1 个月补齐关键技能，并完成 1 个可投递项目。")
    parser.add_argument("--target-job", dest="target_job", default="数据分析师")
    parser.add_argument("--skill", default=None)
    parser.add_argument("--query", default=None, help="If provided, run once and exit.")
    args = parser.parse_args()

    kb = MilvusJobKnowledgeBase()
    agent = LangChainCareerAgent(knowledge_searcher=kb.search)

    print("知识库配置：", kb.describe())
    if args.query:
        run_once(agent, args)
        return
    run_interactive(agent, args)


if __name__ == "__main__":
    main()
