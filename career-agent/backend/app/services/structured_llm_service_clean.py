from __future__ import annotations

import json
import socket
import ssl
from copy import deepcopy
from dataclasses import dataclass
from time import perf_counter, sleep
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services.llm_service import build_llm_call_meta
from app.schemas.portrait import (
    DIMENSION_KEY_ORDER,
    MATCH_DIMENSION_KEY_ORDER,
    JobPortraitSchema,
    StudentPortraitSchema,
)


DIMENSION_LABELS = {
    "professional_skill": "专业技能",
    "certificate": "证书要求",
    "innovation": "创新能力",
    "learning": "学习能力",
    "stress_resistance": "抗压能力",
    "communication": "沟通能力",
    "internship": "实习能力",
}

DEFAULT_MATCH_WEIGHTS = {
    "basic_requirement": 0.25,
    "professional_skill": 0.40,
    "professional_literacy": 0.20,
    "development_potential": 0.15,
}


def _is_transient_network_error(exc: URLError) -> bool:
    reason = getattr(exc, "reason", None)
    text = str(reason or exc).lower()
    return isinstance(reason, (ssl.SSLError, TimeoutError, socket.timeout, ConnectionResetError, ConnectionAbortedError, OSError)) or any(
        token in text
        for token in (
            "unexpected_eof",
            "unexpected eof",
            "eof occurred",
            "connection reset",
            "connection aborted",
            "remote end closed",
            "remote disconnected",
            "temporarily unavailable",
            "timed out",
            "timeout",
            "tls",
            "ssl",
        )
    )


def _dimension_scores(score_map: dict[str, float], description: str) -> list[dict[str, Any]]:
    return [
        {
            "key": key,
            "label": DIMENSION_LABELS[key],
            "score": round(float(score_map.get(key, 60)), 1),
            "description": description,
        }
        for key in DIMENSION_KEY_ORDER
    ]


def _job_template(
    *,
    name: str,
    category: str,
    industry: str,
    summary: str,
    work_content: str,
    core_skills: list[str],
    common_skills: list[str],
    certificates: list[str],
    recommended_courses: list[str],
    score_map: dict[str, float],
    vertical_path: list[dict[str, Any]],
    transfer_paths: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "job_name": name,
        "category": category,
        "industry": industry,
        "summary": summary,
        "core_skills": core_skills,
        "common_skills": common_skills,
        "certificates": certificates,
        "degree_requirement": "本科及以上",
        "major_requirement": "计算机、软件、数据、管理、设计、营销等相关专业优先",
        "internship_requirement": "至少 1 段相关项目或实习经历",
        "work_content": work_content,
        "development_direction": " -> ".join(item["job_name"] for item in vertical_path),
        "recommended_courses": recommended_courses,
        "portrait_dimensions": _dimension_scores(score_map, f"{name}岗位能力维度要求"),
        "vertical_path": vertical_path,
        "transfer_paths": transfer_paths,
        "match_weights": deepcopy(DEFAULT_MATCH_WEIGHTS),
        "source_companies": [],
    }


OFFICIAL_JOB_FAMILY: dict[str, dict[str, Any]] = {
    "Java开发工程师": _job_template(
        name="Java开发工程师",
        category="开发",
        industry="互联网",
        summary="负责后端业务开发、接口设计与系统稳定性优化。",
        work_content="参与业务系统后端模块开发、接口联调、数据库设计与性能优化。",
        core_skills=["Java", "Spring Boot", "MySQL", "Redis", "RESTful API"],
        common_skills=["问题拆解", "代码规范", "跨团队协作"],
        certificates=["软件设计师", "数据库系统工程师"],
        recommended_courses=["Java企业级开发", "Spring Boot实战", "数据库性能优化"],
        score_map={"professional_skill": 88, "certificate": 76, "innovation": 72, "learning": 84, "stress_resistance": 80, "communication": 75, "internship": 86},
        vertical_path=[
            {"level": "初级", "job_name": "Java开发工程师", "description": "独立完成业务模块开发与接口联调。", "requirements": ["Java基础扎实", "掌握Spring Boot", "理解数据库建模"], "promotion_condition": "连续两个迭代稳定交付且无高危缺陷", "path_note": "先稳定交付，再承担复杂模块。"},
            {"level": "中级", "job_name": "高级Java开发工程师", "description": "负责核心模块与系统性能优化。", "requirements": ["复杂业务建模", "性能调优", "技术方案设计"], "promotion_condition": "主导至少一个核心模块并达成指标", "path_note": "从实现者升级为方案设计者。"},
            {"level": "高级", "job_name": "技术负责人/架构师", "description": "负责系统架构与技术治理。", "requirements": ["架构设计", "稳定性治理", "技术决策能力"], "promotion_condition": "完成跨系统架构升级并形成复用能力", "path_note": "转向团队级技术治理与架构决策。"},
        ],
        transfer_paths=[
            {"target_job_name": "测试工程师", "relation_type": "换岗路径", "path_note": "利用接口和代码理解能力转向自动化测试。", "required_skills": ["接口测试", "自动化测试", "质量分析"]},
            {"target_job_name": "运维工程师", "relation_type": "换岗路径", "path_note": "结合发布稳定性经验转向SRE方向。", "required_skills": ["Linux", "Docker", "监控告警"]},
            {"target_job_name": "数据分析师", "relation_type": "换岗路径", "path_note": "利用数据建模基础转向数据分析。", "required_skills": ["SQL", "数据清洗", "统计分析"]},
        ],
    ),
    "前端开发工程师": _job_template(
        name="前端开发工程师",
        category="开发",
        industry="互联网",
        summary="负责 Web 应用前端实现、交互体验与工程化建设。",
        work_content="完成页面开发、组件封装、状态管理与前后端联调。",
        core_skills=["Vue 3", "TypeScript", "JavaScript", "HTML/CSS", "工程化构建"],
        common_skills=["交互理解", "协同推进", "质量意识"],
        certificates=["前端工程化认证"],
        recommended_courses=["Vue 3项目实战", "TypeScript工程化", "前端性能优化"],
        score_map={"professional_skill": 86, "certificate": 68, "innovation": 78, "learning": 84, "stress_resistance": 76, "communication": 80, "internship": 84},
        vertical_path=[
            {"level": "初级", "job_name": "前端开发工程师", "description": "完成页面和组件开发并保障交付质量。", "requirements": ["掌握Vue 3", "接口联调能力", "组件化思维"], "promotion_condition": "连续完成迭代交付并通过代码评审", "path_note": "夯实交付稳定性与组件能力。"},
            {"level": "中级", "job_name": "高级前端工程师", "description": "负责复杂交互、性能优化与工程规范。", "requirements": ["工程化治理", "性能优化", "复杂交互设计"], "promotion_condition": "主导组件体系或性能专项并落地", "path_note": "从页面实现升级到平台能力建设。"},
            {"level": "高级", "job_name": "前端负责人", "description": "负责前端技术路线与团队协同。", "requirements": ["架构能力", "规范治理", "跨团队推动"], "promotion_condition": "建立团队级规范并持续产生收益", "path_note": "转向组织级前端治理。"},
        ],
        transfer_paths=[
            {"target_job_name": "UI设计师", "relation_type": "换岗路径", "path_note": "基于交互实现经验转向体验设计。", "required_skills": ["Figma", "交互设计", "设计规范"]},
            {"target_job_name": "产品经理", "relation_type": "换岗路径", "path_note": "从需求实现走向需求设计与推进。", "required_skills": ["需求分析", "原型设计", "项目推进"]},
            {"target_job_name": "Java开发工程师", "relation_type": "换岗路径", "path_note": "强化后端能力后可转全栈方向。", "required_skills": ["Java", "Spring Boot", "数据库设计"]},
        ],
    ),
    "数据分析师": _job_template(
        name="数据分析师",
        category="数据",
        industry="互联网",
        summary="负责业务数据分析、指标建模与决策支持。",
        work_content="进行数据清洗、统计分析、可视化展示和业务洞察输出。",
        core_skills=["Python", "SQL", "数据清洗", "数据可视化", "统计分析"],
        common_skills=["业务理解", "结构化表达", "跨部门协作"],
        certificates=["数据分析师认证"],
        recommended_courses=["Python数据分析", "SQL进阶", "商业分析方法"],
        score_map={"professional_skill": 86, "certificate": 72, "innovation": 75, "learning": 88, "stress_resistance": 74, "communication": 78, "internship": 82},
        vertical_path=[
            {"level": "初级", "job_name": "数据分析师", "description": "完成数据处理与专题分析交付。", "requirements": ["Python/SQL基础", "可视化能力", "指标理解"], "promotion_condition": "独立输出分析专题并支持业务决策", "path_note": "先建立分析闭环再扩展模型能力。"},
            {"level": "中级", "job_name": "高级数据分析师", "description": "负责模型方案、策略验证与增长分析。", "requirements": ["统计建模", "AB测试", "策略分析"], "promotion_condition": "持续支撑业务增长专项并验证成效", "path_note": "从报表分析升级到策略支撑。"},
            {"level": "高级", "job_name": "数据策略经理", "description": "负责分析体系规划与团队协同。", "requirements": ["分析体系设计", "业务洞察", "跨团队推进"], "promotion_condition": "建立可复用的数据决策框架", "path_note": "转向组织级数据策略治理。"},
        ],
        transfer_paths=[
            {"target_job_name": "产品经理", "relation_type": "换岗路径", "path_note": "将数据洞察能力迁移到产品决策。", "required_skills": ["需求分析", "指标体系", "用户研究"]},
            {"target_job_name": "市场营销专员", "relation_type": "换岗路径", "path_note": "将分析能力迁移到增长营销。", "required_skills": ["用户分层", "投放复盘", "营销分析"]},
            {"target_job_name": "Java开发工程师", "relation_type": "换岗路径", "path_note": "补齐工程能力后转向数据工程开发。", "required_skills": ["Java", "后端开发", "数据仓库"]},
        ],
    ),
}

OFFICIAL_JOB_FAMILY.update(
    {
        "产品经理": _job_template(
            name="产品经理",
            category="产品",
            industry="互联网",
            summary="负责需求拆解、产品规划与跨团队项目推进。",
            work_content="开展需求分析、原型设计、方案评审和上线复盘。",
            core_skills=["需求分析", "原型设计", "PRD", "项目推进", "用户研究"],
            common_skills=["沟通协同", "逻辑拆解", "业务判断"],
            certificates=["NPDP"],
            recommended_courses=["产品需求方法", "原型设计实战", "产品增长策略"],
            score_map={"professional_skill": 83, "certificate": 66, "innovation": 80, "learning": 83, "stress_resistance": 78, "communication": 90, "internship": 79},
            vertical_path=[
                {"level": "初级", "job_name": "产品经理", "description": "负责模块需求交付与版本推进。", "requirements": ["需求拆解", "原型表达", "评审推进"], "promotion_condition": "连续交付核心需求并完成效果复盘", "path_note": "先形成需求到上线闭环。"},
                {"level": "中级", "job_name": "高级产品经理", "description": "负责产品线策略与指标优化。", "requirements": ["产品策略", "数据分析", "跨团队协同"], "promotion_condition": "主导产品线迭代并达成关键目标", "path_note": "从执行走向策略设计。"},
                {"level": "高级", "job_name": "产品负责人", "description": "负责产品路线与组织协同。", "requirements": ["商业理解", "优先级决策", "资源协调"], "promotion_condition": "建立稳定产品节奏并持续增长", "path_note": "转向组织级产品治理。"},
            ],
            transfer_paths=[
                {"target_job_name": "数据分析师", "relation_type": "换岗路径", "path_note": "将数据洞察能力迁移到产品决策。", "required_skills": ["SQL", "实验设计", "业务分析"]},
                {"target_job_name": "市场营销专员", "relation_type": "换岗路径", "path_note": "将用户洞察迁移到增长营销。", "required_skills": ["营销策划", "渠道分析", "增长运营"]},
                {"target_job_name": "前端开发工程师", "relation_type": "换岗路径", "path_note": "具备工程基础可转产品技术方向。", "required_skills": ["Vue 3", "交互实现", "工程协作"]},
            ],
        ),
        "UI设计师": _job_template(
            name="UI设计师",
            category="设计",
            industry="互联网",
            summary="负责界面视觉、交互方案与设计系统建设。",
            work_content="完成视觉设计、交互优化、规范沉淀与交付验收。",
            core_skills=["Figma", "视觉设计", "交互设计", "设计系统", "用户体验"],
            common_skills=["审美表达", "需求理解", "协作沟通"],
            certificates=["UI设计师认证"],
            recommended_courses=["UI视觉体系", "交互设计方法", "设计系统实践"],
            score_map={"professional_skill": 84, "certificate": 64, "innovation": 88, "learning": 80, "stress_resistance": 74, "communication": 79, "internship": 75},
            vertical_path=[
                {"level": "初级", "job_name": "UI设计师", "description": "完成基础视觉与交互交付。", "requirements": ["Figma", "视觉规范", "设计走查"], "promotion_condition": "持续高质量交付并通过验收", "path_note": "先稳定交付，再沉淀系统能力。"},
                {"level": "中级", "job_name": "资深体验设计师", "description": "负责复杂流程与设计系统。", "requirements": ["交互策略", "系统化设计", "跨端一致性"], "promotion_condition": "主导设计系统建设并落地", "path_note": "从页面设计升级到体系设计。"},
                {"level": "高级", "job_name": "设计负责人", "description": "负责设计方向与团队协同。", "requirements": ["设计策略", "组织协同", "团队指导"], "promotion_condition": "形成团队级设计规范并带来业务收益", "path_note": "转向组织级设计治理。"},
            ],
            transfer_paths=[
                {"target_job_name": "前端开发工程师", "relation_type": "换岗路径", "path_note": "补齐工程实现能力后可转前端。", "required_skills": ["HTML/CSS", "Vue 3", "组件开发"]},
                {"target_job_name": "产品经理", "relation_type": "换岗路径", "path_note": "从体验方案延展到需求管理。", "required_skills": ["需求分析", "用户研究", "项目推进"]},
            ],
        ),
        "测试工程师": _job_template(
            name="测试工程师",
            category="测试",
            industry="互联网",
            summary="负责功能质量保障、缺陷治理与自动化测试建设。",
            work_content="执行测试计划、接口测试、自动化脚本与质量复盘。",
            core_skills=["测试用例设计", "接口测试", "自动化测试", "缺陷管理", "SQL"],
            common_skills=["风险意识", "细节管理", "沟通反馈"],
            certificates=["软件测试工程师认证"],
            recommended_courses=["软件测试基础", "接口自动化", "质量工程实践"],
            score_map={"professional_skill": 82, "certificate": 72, "innovation": 68, "learning": 79, "stress_resistance": 86, "communication": 74, "internship": 83},
            vertical_path=[
                {"level": "初级", "job_name": "测试工程师", "description": "负责用例执行与缺陷跟踪。", "requirements": ["测试流程", "缺陷管理", "接口验证"], "promotion_condition": "迭代质量达标并稳定输出测试报告", "path_note": "夯实执行能力与质量意识。"},
                {"level": "中级", "job_name": "高级测试工程师", "description": "负责自动化体系与质量方案。", "requirements": ["自动化框架", "质量分析", "风险预警"], "promotion_condition": "自动化覆盖率持续提升并有效降本", "path_note": "从执行升级到体系建设。"},
                {"level": "高级", "job_name": "测试负责人", "description": "负责测试策略与质量治理。", "requirements": ["测试策略", "跨团队协作", "质量治理"], "promotion_condition": "建立团队级质量体系并稳定运行", "path_note": "转向组织级质量管理。"},
            ],
            transfer_paths=[
                {"target_job_name": "Java开发工程师", "relation_type": "换岗路径", "path_note": "补齐编码与后端能力可转开发。", "required_skills": ["Java", "Spring Boot", "数据库设计"]},
                {"target_job_name": "运维工程师", "relation_type": "换岗路径", "path_note": "利用稳定性经验转向运维。", "required_skills": ["Linux", "监控告警", "发布流程"]},
            ],
        ),
        "运维工程师": _job_template(
            name="运维工程师",
            category="运维",
            industry="互联网",
            summary="负责系统发布、稳定性治理与自动化运维平台建设。",
            work_content="进行部署发布、监控巡检、故障排查和自动化改造。",
            core_skills=["Linux", "Shell", "Docker", "CI/CD", "监控告警"],
            common_skills=["应急响应", "故障定位", "协同推进"],
            certificates=["云计算工程师认证"],
            recommended_courses=["Linux运维", "容器与云原生", "SRE实战"],
            score_map={"professional_skill": 84, "certificate": 78, "innovation": 69, "learning": 82, "stress_resistance": 90, "communication": 73, "internship": 84},
            vertical_path=[
                {"level": "初级", "job_name": "运维工程师", "description": "负责部署巡检与基础故障处理。", "requirements": ["Linux基础", "脚本能力", "监控工具"], "promotion_condition": "发布稳定性持续达标并减少故障", "path_note": "先保障稳定，再推进自动化。"},
                {"level": "中级", "job_name": "高级运维工程师", "description": "负责自动化平台与稳定性优化。", "requirements": ["自动化部署", "容器化", "性能调优"], "promotion_condition": "主导自动化改造并提升效率", "path_note": "从运维执行升级到平台建设。"},
                {"level": "高级", "job_name": "SRE负责人", "description": "负责SLO治理与运维体系建设。", "requirements": ["SLO治理", "故障管理", "跨团队协调"], "promotion_condition": "建立可持续的稳定性治理机制", "path_note": "转向组织级稳定性治理。"},
            ],
            transfer_paths=[
                {"target_job_name": "Java开发工程师", "relation_type": "换岗路径", "path_note": "增强后端开发能力后可转开发岗。", "required_skills": ["Java", "服务治理", "数据库优化"]},
                {"target_job_name": "测试工程师", "relation_type": "换岗路径", "path_note": "可转质量与自动化方向。", "required_skills": ["自动化测试", "质量平台", "故障复盘"]},
            ],
        ),
        "新媒体运营": _job_template(
            name="新媒体运营",
            category="运营",
            industry="消费互联网",
            summary="负责内容运营、活动增长与用户互动。",
            work_content="策划内容矩阵、运营账号、执行活动并复盘效果。",
            core_skills=["内容策划", "账号运营", "活动执行", "数据复盘", "用户增长"],
            common_skills=["文案表达", "执行推进", "沟通协作"],
            certificates=["新媒体运营师认证"],
            recommended_courses=["新媒体运营", "内容增长", "用户运营"],
            score_map={"professional_skill": 79, "certificate": 62, "innovation": 82, "learning": 79, "stress_resistance": 83, "communication": 85, "internship": 77},
            vertical_path=[
                {"level": "初级", "job_name": "新媒体运营", "description": "完成内容发布与活动执行。", "requirements": ["平台规则", "文案能力", "基础复盘"], "promotion_condition": "互动与转化指标持续提升", "path_note": "先形成稳定运营节奏。"},
                {"level": "中级", "job_name": "高级运营", "description": "负责增长项目与策略设计。", "requirements": ["增长策略", "活动策划", "跨团队协作"], "promotion_condition": "主导增长项目达成目标", "path_note": "从执行升级到策略。"},
                {"level": "高级", "job_name": "运营负责人", "description": "负责运营体系与团队协同。", "requirements": ["运营体系", "资源整合", "团队管理"], "promotion_condition": "形成可复用的运营方法论", "path_note": "转向组织级运营治理。"},
            ],
            transfer_paths=[
                {"target_job_name": "市场营销专员", "relation_type": "换岗路径", "path_note": "从内容运营转品牌营销。", "required_skills": ["营销策划", "渠道协同", "品牌传播"]},
                {"target_job_name": "产品经理", "relation_type": "换岗路径", "path_note": "从用户运营转产品增长方向。", "required_skills": ["需求分析", "增长策略", "数据分析"]},
            ],
        ),
        "市场营销专员": _job_template(
            name="市场营销专员",
            category="营销",
            industry="消费互联网",
            summary="负责市场活动、品牌传播与渠道增长。",
            work_content="执行市场活动、品牌传播、渠道协同与结果复盘。",
            core_skills=["市场调研", "活动策划", "品牌传播", "投放复盘", "客户沟通"],
            common_skills=["创意表达", "执行推进", "协作沟通"],
            certificates=["市场营销师认证"],
            recommended_courses=["市场营销基础", "品牌传播", "增长策略实践"],
            score_map={"professional_skill": 79, "certificate": 69, "innovation": 84, "learning": 78, "stress_resistance": 82, "communication": 87, "internship": 76},
            vertical_path=[
                {"level": "初级", "job_name": "市场营销专员", "description": "负责活动执行与投放复盘。", "requirements": ["活动执行", "数据复盘", "客户沟通"], "promotion_condition": "活动转化指标稳定达成", "path_note": "先形成营销执行闭环。"},
                {"level": "中级", "job_name": "高级营销经理", "description": "负责营销策略与渠道整合。", "requirements": ["策略规划", "预算管理", "渠道整合"], "promotion_condition": "主导营销专项达成增长目标", "path_note": "从执行升级到策略。"},
                {"level": "高级", "job_name": "市场负责人", "description": "负责品牌方向与团队经营。", "requirements": ["品牌战略", "组织管理", "经营分析"], "promotion_condition": "持续推动业务增长并沉淀方法论", "path_note": "转向组织级品牌管理。"},
            ],
            transfer_paths=[
                {"target_job_name": "新媒体运营", "relation_type": "换岗路径", "path_note": "转向内容增长与平台运营。", "required_skills": ["内容策划", "平台运营", "用户增长"]},
                {"target_job_name": "产品经理", "relation_type": "换岗路径", "path_note": "将用户洞察迁移到产品策略。", "required_skills": ["用户研究", "需求分析", "增长策略"]},
            ],
        ),
        "人力资源专员": _job_template(
            name="人力资源专员",
            category="职能",
            industry="企业服务",
            summary="负责招聘流程、人才评估与组织协同支持。",
            work_content="开展招聘协同、面试组织、流程管理和数据台账维护。",
            core_skills=["招聘流程", "人才筛选", "面试协同", "员工沟通", "数据台账"],
            common_skills=["组织协调", "流程执行", "服务意识"],
            certificates=["人力资源管理师"],
            recommended_courses=["人力资源管理", "招聘与面试", "组织协同实务"],
            score_map={"professional_skill": 75, "certificate": 79, "innovation": 64, "learning": 77, "stress_resistance": 78, "communication": 91, "internship": 75},
            vertical_path=[
                {"level": "初级", "job_name": "人力资源专员", "description": "负责招聘流程执行与台账管理。", "requirements": ["流程执行", "沟通协调", "基础数据能力"], "promotion_condition": "招聘流程准确率持续达标", "path_note": "先稳定流程执行和协同能力。"},
                {"level": "中级", "job_name": "招聘专员/HRBP", "description": "负责业务招聘与组织支持。", "requirements": ["岗位理解", "面试评估", "业务协同"], "promotion_condition": "支撑关键岗位招聘目标达成", "path_note": "从执行升级到业务赋能。"},
                {"level": "高级", "job_name": "人力资源经理", "description": "负责人力策略与组织发展。", "requirements": ["人才规划", "组织管理", "策略执行"], "promotion_condition": "建立人才发展机制并稳定运行", "path_note": "转向组织级人才治理。"},
            ],
            transfer_paths=[
                {"target_job_name": "市场营销专员", "relation_type": "换岗路径", "path_note": "将沟通与组织能力迁移到市场岗位。", "required_skills": ["活动策划", "品牌沟通", "渠道协作"]},
                {"target_job_name": "产品经理", "relation_type": "换岗路径", "path_note": "从组织需求分析转向业务需求管理。", "required_skills": ["需求分析", "项目推进", "跨团队协作"]},
            ],
        ),
    }
)

ROLE_ALIAS = {
    "java": "Java开发工程师",
    "后端": "Java开发工程师",
    "前端": "前端开发工程师",
    "数据": "数据分析师",
    "产品": "产品经理",
    "ui": "UI设计师",
    "设计": "UI设计师",
    "测试": "测试工程师",
    "运维": "运维工程师",
    "新媒体": "新媒体运营",
    "营销": "市场营销专员",
    "hr": "人力资源专员",
    "人力": "人力资源专员",
}


class ReportSummarySchema(BaseModel):
    summary: str
    highlights: list[str] = Field(default_factory=list)


class PolishSectionSchema(BaseModel):
    polished_content: str


class PolishSummarySchema(BaseModel):
    polished_summary: str


class ResumeProjectRewriteSchema(BaseModel):
    name: str = ""
    role: str = ""
    duration: str = ""
    technologies: list[str] = Field(default_factory=list)
    rewrite: str = ""


class ResumeInternshipRewriteSchema(BaseModel):
    company: str = ""
    position: str = ""
    duration: str = ""
    skills: list[str] = Field(default_factory=list)
    rewrite: str = ""


class ResumeCompetitionSchema(BaseModel):
    name: str = ""
    award: str = ""
    level: str = ""
    description: str = ""


class ResumeCampusExperienceSchema(BaseModel):
    title: str = ""
    role: str = ""
    duration: str = ""
    description: str = ""


class ResumeDocumentSchema(BaseModel):
    title: str = ""
    name: str = ""
    target_role: str = ""
    phone: str = ""
    email: str = ""
    college: str = ""
    major: str = ""
    grade: str = ""
    target_city: str = ""
    summary: str = ""
    education_experience: str = ""
    skills: list[str] = Field(default_factory=list)
    certificates: list[str] = Field(default_factory=list)
    projects: list[ResumeProjectRewriteSchema] = Field(default_factory=list)
    internships: list[ResumeInternshipRewriteSchema] = Field(default_factory=list)
    competitions: list[ResumeCompetitionSchema] = Field(default_factory=list)
    campus_experiences: list[ResumeCampusExperienceSchema] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    recommended_keywords: list[str] = Field(default_factory=list)


class ResumeOptimizationSchema(BaseModel):
    optimized_summary: str = ""
    optimized_projects: list[ResumeProjectRewriteSchema] = Field(default_factory=list)
    optimized_internships: list[ResumeInternshipRewriteSchema] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    recommended_keywords: list[str] = Field(default_factory=list)
    optimized_resume_document: ResumeDocumentSchema = Field(default_factory=ResumeDocumentSchema)


@dataclass(slots=True)
class ProviderConfig:
    provider: str
    model: str
    api_key: str
    base_url: str
    temperature: float


def _normalize_job_key(job_name: str, description: str = "") -> str:
    target = f"{job_name} {description}".lower()
    for official in OFFICIAL_JOB_FAMILY:
        if official.lower() in target:
            return official
    for alias, official in ROLE_ALIAS.items():
        if alias in target:
            return official
    return "产品经理"


def _build_student_profile_template(payload: dict[str, Any]) -> dict[str, Any]:
    skills = payload.get("skills") or []
    certificates = payload.get("certificates") or []
    projects = payload.get("projects") or []
    internships = payload.get("internships") or []
    competitions = payload.get("competitions") or []
    campus_experiences = payload.get("campus_experiences") or []

    score_map = {
        "professional_skill": min(100, 40 + len(skills) * 9 + len(projects) * 5),
        "certificate": min(100, 36 + len(certificates) * 18),
        "innovation": min(100, 38 + len(competitions) * 14 + len(projects) * 4),
        "learning": min(100, 42 + len(projects) * 5 + len(certificates) * 6),
        "stress_resistance": min(100, 40 + len(internships) * 16 + len(projects) * 3),
        "communication": min(100, 42 + len(campus_experiences) * 12 + len(internships) * 6),
        "internship": min(100, 32 + len(internships) * 20 + len(projects) * 6),
    }
    dimensions = _dimension_scores(score_map, "学生能力维度由简历、项目、实习和活动经历综合评估。")
    completeness_score = round(
        min(100, 55 + len(skills) * 4 + len(certificates) * 3 + len(projects) * 5 + len(internships) * 6),
        1,
    )
    competitiveness_score = round(
        score_map["professional_skill"] * 0.24
        + score_map["certificate"] * 0.10
        + score_map["innovation"] * 0.14
        + score_map["learning"] * 0.14
        + score_map["stress_resistance"] * 0.12
        + score_map["communication"] * 0.12
        + score_map["internship"] * 0.14,
        1,
    )
    if competitiveness_score >= 85:
        maturity_level = "高成熟冲刺型"
    elif competitiveness_score >= 72:
        maturity_level = "稳定成长型"
    elif competitiveness_score >= 58:
        maturity_level = "基础提升型"
    else:
        maturity_level = "起步积累型"

    strengths = [item["key"] for item in dimensions if item["score"] >= 78]
    weaknesses = [item["key"] for item in dimensions if item["score"] < 65]
    return {
        "dimensions": dimensions,
        "completeness_score": completeness_score,
        "competitiveness_score": competitiveness_score,
        "maturity_level": maturity_level,
        "ability_tags": [DIMENSION_LABELS[item] for item in strengths[:4]],
        "strengths": strengths or ["learning"],
        "weaknesses": weaknesses or ["certificate"],
        "summary": (
            f"学生画像完整度 {completeness_score} 分，竞争力 {competitiveness_score} 分。"
            f"优势维度集中在 {', '.join(DIMENSION_LABELS[item] for item in (strengths[:2] or ['learning']))}；"
            f"建议优先补齐 {', '.join(DIMENSION_LABELS[item] for item in (weaknesses[:2] or ['certificate']))}。"
        ),
    }


def _clean_json_text(raw_text: str) -> str:
    text = (raw_text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        lines = text.splitlines()
        if lines and lines[0].lower().startswith("json"):
            lines = lines[1:]
        text = "\n".join(lines).strip()
    return text


def _normalize_job_profile_output(payload: dict[str, Any], fallback_job_name: str) -> dict[str, Any]:
    data = deepcopy(payload)
    dimensions = data.get("portrait_dimensions") or []
    dimension_map = {item.get("key"): item for item in dimensions if item.get("key")}
    data["portrait_dimensions"] = [dimension_map[key] for key in DIMENSION_KEY_ORDER if key in dimension_map]
    weights = data.get("match_weights") or {}
    data["match_weights"] = {key: float(weights[key]) for key in MATCH_DIMENSION_KEY_ORDER if key in weights}
    if "source_companies" not in data:
        data["source_companies"] = []
    if not data.get("summary"):
        data["summary"] = f"{fallback_job_name}岗位画像"
    return data


def _normalize_student_profile_output(payload: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(payload)
    dimensions = data.get("dimensions") or []
    dimension_map = {item.get("key"): item for item in dimensions if item.get("key")}
    data["dimensions"] = [dimension_map[key] for key in DIMENSION_KEY_ORDER if key in dimension_map]
    return data


class StructuredLLMService:
    def __init__(self):
        self._last_call_meta: dict[str, Any] = {}

    def generate_job_profile(self, job_name: str, description: str) -> dict[str, Any]:
        raise NotImplementedError

    def generate_student_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def generate_report_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def polish_report_section(self, section_title: str, content: str) -> str:
        raise NotImplementedError

    def polish_report_summary(self, content: str) -> str:
        raise NotImplementedError

    def optimize_resume_content(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def get_last_call_meta(self) -> dict[str, Any]:
        return dict(self._last_call_meta or {})

    def clear_last_call_meta(self) -> None:
        self._last_call_meta = {}

    def _set_last_call_meta(self, meta: dict[str, Any] | None) -> None:
        self._last_call_meta = dict(meta or {})


class MockStructuredLLMService(StructuredLLMService):
    def __init__(self):
        super().__init__()

    def generate_job_profile(self, job_name: str, description: str) -> dict[str, Any]:
        role_key = _normalize_job_key(job_name, description)
        template = deepcopy(OFFICIAL_JOB_FAMILY[role_key])
        template["summary"] = template.get("summary") or f"{job_name}岗位画像"
        template["work_content"] = description or template.get("work_content", "")
        return JobPortraitSchema.model_validate(template).model_dump()

    def generate_student_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        return StudentPortraitSchema.model_validate(_build_student_profile_template(payload)).model_dump()

    def generate_report_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        student_name = payload.get("student_name") or "学生"
        top_job_name = payload.get("top_job_name") or "目标岗位"
        total_score = round(float(payload.get("total_score") or 0), 1)
        summary = {
            "summary": (
                f"{student_name}当前最适配岗位为{top_job_name}，综合匹配度约为 {total_score} 分。"
                "建议围绕基础要求、职业技能、职业素养、发展潜力四个维度持续推进。"
            ),
            "highlights": [
                f"目标岗位：{top_job_name}",
                f"综合匹配：{total_score} 分",
                "优先补齐关键技能与项目证据",
            ],
        }
        return ReportSummarySchema.model_validate(summary).model_dump()

    def polish_report_section(self, section_title: str, content: str) -> str:
        items = [item.strip("，。；; ") for item in content.replace("\n", "。").split("。") if item.strip("，。；; ")]
        merged = "；".join(dict.fromkeys(items)) or content.strip()
        polished = f"{section_title}：{merged}"
        if not polished.endswith("。"):
            polished = f"{polished}。"
        return PolishSectionSchema.model_validate({"polished_content": polished}).polished_content

    def polish_report_summary(self, content: str) -> str:
        items = [item.strip("，。；; ") for item in content.replace("\n", "。").split("。") if item.strip("，。；; ")]
        merged = "；".join(dict.fromkeys(items)) or content.strip()
        if not merged.endswith("。"):
            merged = f"{merged}。"
        return PolishSummarySchema.model_validate({"polished_summary": merged}).polished_summary


    def optimize_resume_content(self, payload: dict[str, Any]) -> dict[str, Any]:
        baseline = deepcopy(payload.get("baseline") or {})
        if not baseline:
            baseline = {
                "optimized_summary": "",
                "optimized_projects": [],
                "optimized_internships": [],
                "highlights": [],
                "issues": [],
                "recommended_keywords": [],
                "optimized_resume_document": {},
            }
        result = ResumeOptimizationSchema.model_validate(baseline).model_dump()
        self._set_last_call_meta(
            build_llm_call_meta(
                provider="mock",
                model_name="mock",
                scene="resume_optimize",
                status="success",
                latency_ms=0.0,
                input_chars=len(json.dumps(payload or {}, ensure_ascii=False)),
                output_chars=len(json.dumps(result or {}, ensure_ascii=False)),
                raw_meta_json={"source": "mock_reference"},
            )
        )
        return result


class OpenAICompatibleStructuredLLMService(StructuredLLMService):
    def __init__(self, config: ProviderConfig):
        super().__init__()
        if not config.api_key:
            raise RuntimeError(f"{config.provider} API key is empty")
        self.config = config

    def generate_job_profile(self, job_name: str, description: str) -> dict[str, Any]:
        role_key = _normalize_job_key(job_name, description)
        reference = deepcopy(OFFICIAL_JOB_FAMILY[role_key])
        payload = self._run_task(
            task_name="job_portrait",
            schema=JobPortraitSchema,
            input_payload={"job_name": job_name, "job_description": description},
            reference_output=reference,
        )
        return JobPortraitSchema.model_validate(_normalize_job_profile_output(payload, job_name)).model_dump()

    def generate_student_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        reference = _build_student_profile_template(payload)
        result = self._run_task(
            task_name="student_portrait",
            schema=StudentPortraitSchema,
            input_payload=payload,
            reference_output=reference,
        )
        return StudentPortraitSchema.model_validate(_normalize_student_profile_output(result)).model_dump()

    def generate_report_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        student_name = payload.get("student_name") or "学生"
        top_job_name = payload.get("top_job_name") or "目标岗位"
        total_score = round(float(payload.get("total_score") or 0), 1)
        reference = {
            "summary": f"{student_name}当前最适配岗位为{top_job_name}，综合匹配度约为 {total_score} 分。",
            "highlights": [f"目标岗位：{top_job_name}", f"综合匹配：{total_score} 分", "建议围绕四大匹配维度持续补齐差距"],
        }
        return self._run_task(
            task_name="report_summary",
            schema=ReportSummarySchema,
            input_payload=payload,
            reference_output=reference,
        )

    def polish_report_section(self, section_title: str, content: str) -> str:
        result = self._run_task(
            task_name="report_polish_section",
            schema=PolishSectionSchema,
            input_payload={"section_title": section_title, "content": content},
            reference_output={"polished_content": f"{section_title}：{content.strip()}"},
        )
        return PolishSectionSchema.model_validate(result).polished_content

    def polish_report_summary(self, content: str) -> str:
        result = self._run_task(
            task_name="report_polish_summary",
            schema=PolishSummarySchema,
            input_payload={"content": content},
            reference_output={"polished_summary": content.strip()},
        )
        return PolishSummarySchema.model_validate(result).polished_summary

    def optimize_resume_content(self, payload: dict[str, Any]) -> dict[str, Any]:
        baseline = deepcopy(payload.get("baseline") or {})
        result = self._run_task(
            task_name="resume_optimize",
            schema=ResumeOptimizationSchema,
            input_payload=payload,
            reference_output=baseline
            or {
                "optimized_summary": "",
                "optimized_projects": [],
                "optimized_internships": [],
                "highlights": [],
                "issues": [],
                "recommended_keywords": [],
                "optimized_resume_document": {},
            },
        )
        return ResumeOptimizationSchema.model_validate(result).model_dump()

    def _run_task(
        self,
        *,
        task_name: str,
        schema: type[BaseModel],
        input_payload: dict[str, Any],
        reference_output: dict[str, Any],
    ) -> dict[str, Any]:
        schema_json = schema.model_json_schema()
        system_prompt = (
            "你是职业规划系统的结构化生成引擎。"
            "输出必须是 JSON 对象，且严格符合给定 schema。"
            "不得输出任何解释文本、Markdown 或代码块。"
        )
        user_prompt = json.dumps(
            {
                "task": task_name,
                "rules": {
                    "portrait_dimensions": list(DIMENSION_KEY_ORDER),
                    "match_dimensions": list(MATCH_DIMENSION_KEY_ORDER),
                    "match_weights_sum": 1.0,
                },
                "input": input_payload,
                "schema": schema_json,
                "reference_output": reference_output,
            },
            ensure_ascii=False,
        )
        raw = self._chat_json(system_prompt, user_prompt)
        return schema.model_validate(raw).model_dump()

    def _chat_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        base_url = self.config.base_url.rstrip("/")
        request_url = f"{base_url}/chat/completions"
        payload = {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        payload_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        settings = get_settings()
        max_attempts = max(1, int(getattr(settings, "LLM_RETRY_MAX_ATTEMPTS", 3) or 3))
        delay = max(0.0, float(getattr(settings, "LLM_RETRY_INITIAL_DELAY_SECONDS", 1.0) or 1.0))
        multiplier = max(1.0, float(getattr(settings, "LLM_RETRY_BACKOFF_MULTIPLIER", 2.0) or 2.0))
        max_delay = max(delay, float(getattr(settings, "LLM_RETRY_MAX_DELAY_SECONDS", 30.0) or 30.0))
        start = perf_counter()
        body = ""
        for attempt in range(1, max_attempts + 1):
            req = Request(
                request_url,
                data=payload_bytes,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.config.api_key}"},
                method="POST",
            )
            try:
                with urlopen(req, timeout=120) as resp:
                    body = resp.read().decode("utf-8")
                break
            except HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="ignore")
                retryable = exc.code == 429 or exc.code >= 500
                if retryable and attempt < max_attempts:
                    sleep(min(delay, max_delay))
                    delay = min(delay * multiplier, max_delay)
                    continue
                self._set_last_call_meta(
                    build_llm_call_meta(
                        provider=self.config.provider,
                        model_name=self.config.model,
                        scene="structured_extract",
                        status="failed",
                        latency_ms=round((perf_counter() - start) * 1000, 2),
                        input_chars=len(user_prompt),
                        output_chars=0,
                        error_message=f"HTTP {exc.code}: {detail}",
                        raw_meta_json={"source": "structured_llm", "attempt": attempt, "retryable": retryable},
                    )
                )
                raise RuntimeError(f"LLM HTTP error {exc.code}: {detail}") from exc
            except URLError as exc:
                retryable = _is_transient_network_error(exc)
                if retryable and attempt < max_attempts:
                    sleep(min(delay, max_delay))
                    delay = min(delay * multiplier, max_delay)
                    continue
                self._set_last_call_meta(
                    build_llm_call_meta(
                        provider=self.config.provider,
                        model_name=self.config.model,
                        scene="structured_extract",
                        status="failed",
                        latency_ms=round((perf_counter() - start) * 1000, 2),
                        input_chars=len(user_prompt),
                        output_chars=0,
                        error_message=f"Network error: {exc.reason}",
                        raw_meta_json={"source": "structured_llm", "attempt": attempt, "retryable": retryable},
                    )
                )
                raise RuntimeError("LLM structured extraction network error") from exc

        data = json.loads(body)
        content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
        if not content:
            self._set_last_call_meta(
                build_llm_call_meta(
                    provider=self.config.provider,
                    model_name=self.config.model,
                    scene="structured_extract",
                    status="failed",
                    latency_ms=round((perf_counter() - start) * 1000, 2),
                    input_chars=len(user_prompt),
                    output_chars=0,
                    error_message="LLM returned empty content",
                    raw_meta_json={"source": "structured_llm"},
                )
            )
            raise RuntimeError("LLM returned empty content")
        parsed_content = json.loads(_clean_json_text(content))
        usage = data.get("usage") or {}
        self._set_last_call_meta(
            build_llm_call_meta(
                provider=self.config.provider,
                model_name=self.config.model,
                scene="structured_extract",
                status="success",
                latency_ms=round((perf_counter() - start) * 1000, 2),
                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                completion_tokens=int(usage.get("completion_tokens") or 0),
                total_tokens=int(usage.get("total_tokens") or 0),
                input_chars=len(user_prompt),
                output_chars=len(content),
                raw_usage_json=usage,
                raw_meta_json={"source": "structured_llm"},
            )
        )
        return parsed_content


def _build_provider_config(
    model_override: str | None = None,
    *,
    api_key_override: str | None = None,
    base_url_override: str | None = None,
) -> ProviderConfig:
    settings = get_settings()
    provider = settings.LLM_PROVIDER.lower().strip()
    if provider == "mock":
        return ProviderConfig(provider="mock", model="mock", api_key="", base_url="", temperature=0.0)
    if provider == "openai":
        return ProviderConfig(
            provider="openai",
            model=model_override if model_override is not None else settings.OPENAI_MODEL,
            api_key=api_key_override if api_key_override is not None else settings.OPENAI_API_KEY,
            base_url=base_url_override if base_url_override is not None else settings.OPENAI_BASE_URL,
            temperature=settings.LLM_TEMPERATURE,
        )
    if provider == "qwen":
        return ProviderConfig(
            provider="qwen",
            model=model_override if model_override is not None else settings.LANGCHAIN_MODEL,
            api_key=api_key_override if api_key_override is not None else settings.DASHSCOPE_API_KEY,
            base_url=base_url_override if base_url_override is not None else settings.LANGCHAIN_BASE_URL,
            temperature=settings.LLM_TEMPERATURE,
        )
    raise RuntimeError(f"Unsupported LLM provider: {settings.LLM_PROVIDER}")


def get_structured_llm_service(
    model_override: str | None = None,
    *,
    api_key_override: str | None = None,
    base_url_override: str | None = None,
) -> StructuredLLMService:
    config = _build_provider_config(
        model_override=model_override,
        api_key_override=api_key_override,
        base_url_override=base_url_override,
    )
    if config.provider == "mock":
        return MockStructuredLLMService()
    return OpenAICompatibleStructuredLLMService(config)


def get_structured_llm_service_for_profile(
    *,
    api_key: str,
    base_url: str,
    module_name: str,
) -> StructuredLLMService:
    return get_structured_llm_service(
        model_override=module_name,
        api_key_override=api_key,
        base_url_override=base_url,
    )


def get_official_job_family() -> dict[str, dict[str, Any]]:
    return deepcopy(OFFICIAL_JOB_FAMILY)
