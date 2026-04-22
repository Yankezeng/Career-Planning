from __future__ import annotations
from typing import Any


JOB_KNOWLEDGE_GRAPH = {
    "产品经理": {
        "category": "产品",
        "aliases": ["产品策划", "Product Manager", "PM", "产品负责人"],
        "related_roles": {
            "entry": ["产品助理", "实习产品经理"],
            "mid": ["产品经理", "高级产品经理"],
            "senior": ["产品总监", "高级产品总监"],
            "adjacent": ["产品运营", "项目经理", "数据分析"]
        },
        "excluded_similarity": {
            "reason": "职能差异大",
            "roles": ["Java开发", "Python开发", "前端开发", "后端开发",
                     "算法工程师", "测试工程师", "运维工程师"]
        },
        "skill_tree": {
            "core": ["需求分析", "产品设计", "项目管理", "数据分析", "用户研究"],
            "tools": ["Axure", "Figma", "Sketch", "XMind", "SQL", "Python"],
            "soft": ["沟通协作", "逻辑思维", "执行力", "创新能力"]
        },
        "education": "本科及以上，专业不限",
        "experience": "1-3年产品经验或相关实习"
    },
    "前端开发": {
        "category": "开发",
        "aliases": ["前端工程师", "Web开发", "FE"],
        "related_roles": {
            "entry": ["前端实习生", "初级前端开发"],
            "mid": ["前端开发", "高级前端开发"],
            "senior": ["前端专家", "前端架构师"],
            "adjacent": ["全栈开发", "Node.js开发", "移动端开发"]
        },
        "excluded_similarity": {
            "reason": "职能差异大",
            "roles": ["产品经理", "UI设计", "UX设计", "运营", "销售"]
        },
        "skill_tree": {
            "core": ["HTML/CSS", "JavaScript", "TypeScript", "框架(React/Vue)"],
            "tools": ["Git", "Webpack", "Vite", "npm", "Chrome DevTools"],
            "soft": ["代码规范", "性能意识", "协作沟通"]
        },
        "education": "本科及以上，计算机相关优先",
        "experience": "1-3年开发经验"
    },
    "后端开发": {
        "category": "开发",
        "aliases": ["后端工程师", "服务器开发", "BE"],
        "related_roles": {
            "entry": ["后端实习生", "初级后端开发"],
            "mid": ["后端开发", "高级后端开发"],
            "senior": ["后端专家", "架构师"],
            "adjacent": ["全栈开发", "数据工程师", "运维工程师"]
        },
        "excluded_similarity": {
            "reason": "职能差异大",
            "roles": ["产品经理", "UI设计", "UX设计", "运营", "销售"]
        },
        "skill_tree": {
            "core": ["Java/Python/Go", "数据库", "API设计", "微服务"],
            "tools": ["Git", "Docker", "Kubernetes", "Redis", "MQ"],
            "soft": ["架构思维", "性能优化", "团队协作"]
        },
        "education": "本科及以上，计算机相关",
        "experience": "1-3年开发经验"
    },
    "数据分析师": {
        "category": "数据",
        "aliases": ["数据分析工程师", "DA", "BI工程师"],
        "related_roles": {
            "entry": ["数据分析师助理", "实习数据分析师"],
            "mid": ["数据分析师", "高级数据分析师"],
            "senior": ["数据科学家", "首席数据分析师"],
            "adjacent": ["算法工程师", "数据工程师", "产品经理"]
        },
        "excluded_similarity": {
            "reason": "职能差异大",
            "roles": ["前端开发", "后端开发", "UI设计", "销售"]
        },
        "skill_tree": {
            "core": ["SQL", "Python", "数据分析", "统计学"],
            "tools": ["Excel", "PowerBI", "Tableau", "Hive"],
            "soft": ["业务理解", "逻辑思维", "沟通表达"]
        },
        "education": "本科及以上，统计/数学/计算机相关",
        "experience": "1-3年分析经验"
    },
    "算法工程师": {
        "category": "开发",
        "aliases": ["算法研发工程师", "AI工程师", "机器学习工程师"],
        "related_roles": {
            "entry": ["算法实习生", "初级算法工程师"],
            "mid": ["算法工程师", "高级算法工程师"],
            "senior": ["算法专家", "研究员"],
            "adjacent": ["数据工程师", "数据科学家", "产品经理"]
        },
        "excluded_similarity": {
            "reason": "职能差异大",
            "roles": ["产品经理", "UI设计", "运营", "销售"]
        },
        "skill_tree": {
            "core": ["机器学习", "深度学习", "NLP", "CV", "推荐系统"],
            "tools": ["TensorFlow", "PyTorch", "Spark", "SQL"],
            "soft": ["数学基础", "论文阅读", "工程落地"]
        },
        "education": "硕士及以上，计算机/数学/统计相关",
        "experience": "1-3年算法经验"
    },
    "运营": {
        "category": "运营",
        "aliases": ["运营专员", "运营经理", "用户运营", "内容运营"],
        "related_roles": {
            "entry": ["运营助理", "实习运营"],
            "mid": ["运营专员", "运营经理", "高级运营"],
            "senior": ["运营总监", "COO"],
            "adjacent": ["产品运营", "市场营销", "项目管理"]
        },
        "excluded_similarity": {
            "reason": "职能差异大",
            "roles": ["前端开发", "后端开发", "算法工程师"]
        },
        "skill_tree": {
            "core": ["用户运营", "内容运营", "活动运营", "数据运营"],
            "tools": ["Excel", "SQL", "数据分析平台", "社群工具"],
            "soft": ["沟通协作", "创新能力", "执行力"]
        },
        "education": "本科及以上，专业不限",
        "experience": "1-3年运营经验"
    },
    "市场营销": {
        "category": "营销",
        "aliases": ["市场专员", "市场经理", "品牌营销", "数字营销"],
        "related_roles": {
            "entry": ["市场助理", "实习市场"],
            "mid": ["市场营销", "市场经理"],
            "senior": ["市场总监", "CMO"],
            "adjacent": ["运营", "销售", "公关"]
        },
        "excluded_similarity": {
            "reason": "职能差异大",
            "roles": ["前端开发", "后端开发", "算法工程师"]
        },
        "skill_tree": {
            "core": ["品牌营销", "数字营销", "市场分析", "渠道管理"],
            "tools": ["Google Analytics", "SEO/SEM", "社交媒体", "CRM"],
            "soft": ["创意策划", "沟通谈判", "数据分析"]
        },
        "education": "本科及以上，市场/广告/传播相关",
        "experience": "1-3年市场经验"
    }
}


class JobKnowledgeGraph:
    def __init__(self):
        self.graph = JOB_KNOWLEDGE_GRAPH

    def get_job_info(self, job_name: str) -> dict[str, Any] | None:
        normalized = self._normalize_job_name(job_name)
        return self.graph.get(normalized)

    def _normalize_job_name(self, name: str) -> str | None:
        name = name.strip().lower().replace(" ", "")
        for job, info in self.graph.items():
            if job.lower().replace(" ", "") == name:
                return job
            for alias in info.get("aliases", []):
                if alias.lower().replace(" ", "") == name:
                    return job
        return None

    def get_related_jobs(self, job_name: str) -> list[str]:
        info = self.get_job_info(job_name)
        if not info:
            return []
        related = info.get("related_roles", {})
        result = []
        for level in related.values():
            result.extend(level)
        return result

    def get_excluded_jobs(self, job_name: str) -> list[str]:
        info = self.get_job_info(job_name)
        if not info:
            return []
        return info.get("excluded_similarity", {}).get("roles", [])

    def get_skill_tree(self, job_name: str) -> dict[str, list[str]]:
        info = self.get_job_info(job_name)
        if not info:
            return {"core": [], "tools": [], "soft": []}
        return info.get("skill_tree", {"core": [], "tools": [], "soft": []})

    def get_job_category(self, job_name: str) -> str | None:
        info = self.get_job_info(job_name)
        return info.get("category") if info else None

    def filter_search_results(self, job_name: str,
                               search_results: list[dict]) -> list[dict]:
        excluded = self.get_excluded_jobs(job_name)
        if not excluded:
            return search_results

        target_category = self.get_job_category(job_name)

        filtered = [
            r for r in search_results
            if r.get("job_name") not in excluded
        ]

        if target_category:
            categorized = [r for r in filtered
                         if r.get("job_category", "").lower() == target_category.lower()]
            uncategorized = [r for r in filtered
                           if r.get("job_category", "").lower() != target_category.lower()]
            filtered = categorized + uncategorized

        return filtered


_job_graph_instance = None

def get_job_knowledge_graph() -> JobKnowledgeGraph:
    global _job_graph_instance
    if _job_graph_instance is None:
        _job_graph_instance = JobKnowledgeGraph()
    return _job_graph_instance
