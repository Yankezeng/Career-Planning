from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models.career import CareerPath, CareerPathTask
from app.models.job import Job
from app.models.student import Student
from app.services.job_match_service_clean import JobMatchService
from app.services.student_profile_service_clean import StudentProfileService
from app.services.structured_llm_service_clean import get_official_job_family
from app.utils.serializers import to_dict
from app.services.graph.neo4j_service import get_neo4j_service, Neo4jService


class CareerPathNeo4jService:
    def __init__(self, neo4j_service: Neo4jService | None = None):
        self.graph = neo4j_service or get_neo4j_service()

    def create_career_path(
        self,
        from_job_id: int,
        to_job_id: int,
        years_required: float,
        salary_boost: float = 0.0,
        difficulty: str = "intermediate",
    ) -> bool:
        cypher = """
        MATCH (a:Job {job_id: $from_id})
        MATCH (b:Job {job_id: $to_id})
        CREATE (a)-[r:NEXT {years_required: $years, salary_boost: $salary_boost, difficulty: $difficulty}]->(b)
        RETURN count(r) AS created
        """
        params = {
            "from_id": from_job_id,
            "to_id": to_job_id,
            "years": years_required,
            "salary_boost": salary_boost,
            "difficulty": difficulty,
        }
        result = self.graph.execute_single(cypher, params)
        return result.get("created", 0) > 0 if result else False

    def get_career_paths(
        self,
        start_job_id: int,
        max_hops: int = 5,
        max_paths: int = 10,
    ) -> list[dict[str, Any]]:
        cypher = f"""
        MATCH path = (start:Job {{job_id: $start_id}})-[:NEXT*1..{max_hops}]->(end:Job)
        WHERE start <> end
        WITH path, end, start,
             REDUCE(total_years = 0.0, r IN relationships(path) | total_years + r.years_required) AS total_years,
             REDUCE(total_salary = 0.0, r IN relationships(path) | total_salary + r.salary_boost) AS total_salary_boost,
             REDUCE(max_diff = '', r IN relationships(path) | CASE WHEN r.difficulty = 'hard' THEN r.difficulty ELSE max_diff END) AS max_difficulty
        RETURN end.job_id AS target_job_id,
               end.name AS target_job_name,
               total_years,
               total_salary_boost,
               max_difficulty,
               REDUCE(names = [], n IN nodes(path) | names + {{job_id: n.job_id, name: n.name}}) AS path_nodes,
               length(path) AS hops
        ORDER BY total_years ASC
        LIMIT $max_paths
        """
        return self.graph.execute_query(cypher, {"start_id": start_job_id, "max_paths": max_paths})

    def get_alternative_paths(
        self,
        start_job_id: int,
        target_job_id: int,
        max_hops: int = 5,
    ) -> list[dict[str, Any]]:
        cypher = f"""
        MATCH path = (start:Job {{job_id: $start_id}})-[:NEXT*1..{max_hops}]->(target:Job {{job_id: $target_id}})
        WITH path, target, start,
             REDUCE(total_years = 0.0, r IN relationships(path) | total_years + r.years_required) AS total_years
        RETURN target.job_id AS target_job_id,
               target.name AS target_job_name,
               total_years,
               REDUCE(names = [], n IN nodes(path) | names + {{job_id: n.job_id, name: n.name}}) AS path_nodes,
               REDUCE(rels = [], r IN relationships(path) | rels + {{years: r.years_required, difficulty: r.difficulty}}) AS path_relations,
               length(path) AS hops
        ORDER BY total_years
        """
        return self.graph.execute_query(
            cypher,
            {"start_id": start_job_id, "target_id": target_job_id}
        )

    def get_promotion_chain(self, job_id: int, direction: str = "up", max_depth: int = 5) -> list[dict[str, Any]]:
        if direction == "up":
            cypher = f"""
            MATCH path = (j:Job {{job_id: $job_id}})-[:NEXT*1..{max_depth}]->(next_j:Job)
            WITH path, next_j,
                 REDUCE(years = 0.0, r IN relationships(path) | years + r.years_required) AS total_years
            RETURN next_j.job_id AS job_id,
                   next_j.name AS name,
                   total_years,
                   length(path) AS steps
            ORDER BY steps
            """
        else:
            cypher = f"""
            MATCH path = (prev_j:Job)-[:NEXT*1..{max_depth}]->(j:Job {{job_id: $job_id}})
            WITH path, prev_j,
                 REDUCE(years = 0.0, r IN relationships(path) | years + r.years_required) AS total_years
            RETURN prev_j.job_id AS job_id,
                   prev_j.name AS name,
                   total_years,
                   length(path) AS steps
            ORDER BY steps
            """
        return self.graph.execute_query(cypher, {"job_id": job_id})

    def get_transfer_paths(
        self,
        from_job_id: int,
        to_job_id: int,
        max_hops: int = 3,
    ) -> list[dict[str, Any]]:
        cypher = f"""
        MATCH path = (a:Job {{job_id: $from_id}})-[:NEXT*1..{max_hops}]->(b:Job {{job_id: $to_id}})
        WITH path, a, b,
             REDUCE(total = 0.0, r IN relationships(path) | total + r.years_required) AS total_years
        RETURN b.job_id AS target_job_id,
               b.name AS target_job_name,
               total_years,
               REDUCE(names = [], n IN nodes(path) | names + {{job_id: n.job_id, name: n.name}}) AS path,
               length(path) AS hops
        ORDER BY total_years
        """
        return self.graph.execute_query(cypher, {"from_id": from_job_id, "to_id": to_job_id})

    def get_all_career_transitions(self, job_id: int) -> dict[str, Any]:
        cypher = """
        MATCH (j:Job {job_id: $job_id})
        OPTIONAL MATCH (j)-[:NEXT]->(next_j:Job)
        OPTIONAL MATCH (prev_j:Job)-[:NEXT]->(j)
        RETURN j.job_id AS job_id,
               j.name AS name,
               COLLECT(DISTINCT {job_id: next_j.job_id, name: next_j.name}) AS promotions,
               COLLECT(DISTINCT {job_id: prev_j.job_id, name: prev_j.name}) AS prerequisites
        """
        result = self.graph.execute_single(cypher, {"job_id": job_id})
        if result:
            result["promotions"] = [p for p in result.get("promotions", []) if p.get("job_id")]
            result["prerequisites"] = [p for p in result.get("prerequisites", []) if p.get("job_id")]
        return result or {}

    def simulate_career_paths(
        self,
        start_job_id: int,
        target_job_id: int,
        student_skills: list[int],
    ) -> list[dict[str, Any]]:
        cypher = """
        MATCH (start:Job {job_id: $start_id})
        MATCH (target:Job {job_id: $target_id})
        MATCH path = (start)-[:NEXT*1..8]->(target)
        WITH path, target, start,
             REDUCE(years = 0.0, r IN relationships(path) | years + r.years_required) AS total_years
        MATCH (st:Student {student_id: $student_id})
        OPTIONAL MATCH (st)-[:KNOWS]->(s:Skill)<-[:REQUIRES]-(j:Job)
        WHERE j IN nodes(path)
        WITH path, target, total_years, collect(DISTINCT s.name) AS student_skills_list
        RETURN target.job_id AS target_job_id,
               target.name AS target_job_name,
               total_years,
               REDUCE(names = [], n IN nodes(path) | names + {job_id: n.job_id, name: n.name}) AS path,
               length(path) AS hops,
               student_skills_list
        ORDER BY total_years
        LIMIT 5
        """
        return self.graph.execute_query(
            cypher,
            {"start_id": start_job_id, "target_id": target_job_id, "student_id": student_skills}
        )

    def delete_career_path(self, from_job_id: int, to_job_id: int) -> bool:
        cypher = """
        MATCH (a:Job {job_id: $from_id})-[r:NEXT]->(b:Job {job_id: $to_id})
        DELETE r
        RETURN count(r) AS deleted
        """
        result = self.graph.execute_single(cypher, {"from_id": from_job_id, "to_id": to_job_id})
        return result.get("deleted", 0) > 0 if result else False


def get_career_path_neo4j_service() -> CareerPathNeo4jService:
    return CareerPathNeo4jService()


class CareerPathService:
    def __init__(self, db: Session = None):
        self.db = db
        self.neo4j_service = CareerPathNeo4jService()
        self.match_service = JobMatchService(db) if db else None
        self.profile_service = StudentProfileService(db) if db else None

    def generate_path(self, student_id: int, target_job_id: int = None) -> dict[str, Any]:
        student = (
            self.db.query(Student)
            .options(
                joinedload(Student.skills),
                joinedload(Student.certificates),
                joinedload(Student.projects),
                joinedload(Student.internships),
            )
            .filter(Student.id == student_id, Student.deleted.is_(False))
            .first()
        )
        if not student:
            raise ValueError("学生不存在")

        if target_job_id:
            job = self.db.query(Job).filter(Job.id == target_job_id, Job.deleted.is_(False)).first()
            if not job:
                raise ValueError("目标岗位不存在")
        else:
            matches = self.match_service.get_matches(student_id) or self.match_service.generate_matches(student_id)
            if not matches:
                raise ValueError("无法获取岗位匹配结果")
            job = self.db.query(Job).filter(Job.id == matches[0]["job_id"], Job.deleted.is_(False)).first()
            if not job:
                raise ValueError("目标岗位不存在")

        student_skills = {item.name.lower() for item in student.skills if not item.deleted}
        project_skills = {skill.lower() for item in student.projects if not item.deleted for skill in (item.technologies or [])}
        internship_skills = {skill.lower() for item in student.internships if not item.deleted for skill in (item.skills or [])}
        all_student_skills = student_skills | project_skills | internship_skills

        required_skills = set(job.core_skill_tags or [])
        job_profile = job.job_profile if isinstance(job.job_profile, dict) else {}
        if job_profile.get("core_skills"):
            required_skills |= set(job_profile["core_skills"])

        skill_gaps = sorted(required_skills - all_student_skills)

        vertical_path = job_profile.get("vertical_path") or self._resolve_vertical_path(job.name)
        transfer_paths = job_profile.get("transfer_paths") or self._resolve_transfer_paths(job.name)

        career_path = (
            self.db.query(CareerPath)
            .filter(CareerPath.student_id == student_id, CareerPath.deleted.is_(False))
            .order_by(CareerPath.id.desc())
            .first()
        )
        if career_path:
            for key, value in {"target_job_id": job.id, "status": "active"}.items():
                setattr(career_path, key, value)
        else:
            career_path = CareerPath(student_id=student_id, target_job_id=job.id, status="active")
            self.db.add(career_path)
        self.db.flush()

        self._clear_old_tasks(career_path.id)
        tasks = self._build_tasks(career_path.id, job, student, vertical_path, skill_gaps, required_skills, all_student_skills)
        self.db.add_all(tasks)

        overview = self._build_overview(job, vertical_path)
        summary = self._build_summary(job, skill_gaps, vertical_path)
        career_path.overview = overview
        career_path.summary = summary

        self.db.commit()
        self.db.refresh(career_path)

        return self._serialize_path(career_path, job)

    def get_latest_path(self, student_id: int) -> dict[str, Any]:
        career_path = (
            self.db.query(CareerPath)
            .options(joinedload(CareerPath.tasks))
            .filter(CareerPath.student_id == student_id, CareerPath.deleted.is_(False), CareerPath.status == "active")
            .order_by(CareerPath.id.desc())
            .first()
        )
        if not career_path:
            return None

        job = None
        if career_path.target_job_id:
            job = self.db.query(Job).filter(Job.id == career_path.target_job_id, Job.deleted.is_(False)).first()

        return self._serialize_path(career_path, job)

    def _resolve_vertical_path(self, job_name: str) -> list[dict[str, Any]]:
        family = get_official_job_family()
        for name, template in family.items():
            if name in job_name or job_name in name:
                return template.get("vertical_path", [])
        return [
            {"level": "初级", "job_name": job_name, "description": "独立完成基础业务模块。", "requirements": ["掌握核心技能"], "promotion_condition": "连续稳定交付", "path_note": "夯实基础能力。"},
            {"level": "中级", "job_name": f"高级{job_name}", "description": "负责复杂模块与优化。", "requirements": ["复杂业务建模", "性能调优"], "promotion_condition": "主导核心模块", "path_note": "从实现者升级为设计者。"},
            {"level": "高级", "job_name": f"{job_name}负责人", "description": "负责技术路线与团队协同。", "requirements": ["架构能力", "团队管理"], "promotion_condition": "建立团队规范", "path_note": "转向组织级治理。"},
        ]

    def _resolve_transfer_paths(self, job_name: str) -> list[dict[str, Any]]:
        family = get_official_job_family()
        for name, template in family.items():
            if name in job_name or job_name in name:
                return template.get("transfer_paths", [])
        return []

    def _clear_old_tasks(self, path_id: int):
        self.db.query(CareerPathTask).filter(CareerPathTask.career_path_id == path_id).delete()

    def _build_tasks(self, path_id: int, job, student, vertical_path, skill_gaps, required_skills, all_student_skills) -> list[CareerPathTask]:
        tasks: list[CareerPathTask] = []
        profile = self.profile_service.get_latest_profile(student.id) if self.profile_service else None
        profile_dimensions = {}
        if profile and isinstance(profile.get("raw_metrics"), dict):
            for item in profile["raw_metrics"].get("dimension_scores", []):
                if item.get("key"):
                    profile_dimensions[item["key"]] = float(item["score"])

        for index, stage in enumerate(vertical_path):
            stage_level = stage.get("level", "")
            stage_label = f"阶段{index + 1}：{stage_level}"

            missing_stage_skills = []
            for skill in skill_gaps:
                if skill not in all_student_skills:
                    missing_stage_skills.append(skill)

            if missing_stage_skills:
                priority = 1 if index == 0 else 2
                tasks.append(CareerPathTask(
                    career_path_id=path_id,
                    stage_label=stage_label,
                    category="学习",
                    title=f"补齐{stage_level}核心技能：{', '.join(missing_stage_skills[:3])}",
                    description=f"围绕 {job.name} 的 {stage_level} 阶段要求，优先掌握 {', '.join(missing_stage_skills[:3])}。",
                    due_hint=stage.get("path_note", ""),
                    priority=priority,
                    weekly_tasks=[f"学习 {skill} 基础概念" for skill in missing_stage_skills[:2]],
                    related_skills=missing_stage_skills[:3],
                    difficulty_level="高" if priority == 1 else "中",
                ))

            tasks.append(CareerPathTask(
                career_path_id=path_id,
                stage_label=stage_label,
                category="项目",
                title=f"{stage_level}项目实践：完成可展示的{job.name}相关项目",
                description=stage.get("description", f"完成与{job.name}相关的实践项目，产出可量化成果。"),
                due_hint=stage.get("promotion_condition", ""),
                priority=2,
                weekly_tasks=["推进项目模块开发", "记录项目进展与问题"],
                related_skills=list(required_skills)[:3],
                difficulty_level="中",
            ))

        internship_score = profile_dimensions.get("internship", 60.0) if profile_dimensions else 60.0
        if internship_score < 70:
            tasks.append(CareerPathTask(
                career_path_id=path_id,
                stage_label="持续",
                category="实习",
                title=f"获取{job.name}相关实习经历",
                description=f"建议参与真实企业项目或实习，积累岗位实践经验。当前实习能力得分 {internship_score} 分，建议提升至 75 分以上。",
                due_hint="建议 3 个月内完成",
                priority=1,
                weekly_tasks=["关注实习机会", "准备实习投递材料"],
                related_skills=list(required_skills)[:3],
                difficulty_level="高",
            ))

        cert_tags = job.certificate_tags or []
        if isinstance(job.job_profile, dict) and job.job_profile.get("certificates"):
            cert_tags = list(set(cert_tags + job.job_profile.get("certificates", [])))
        if cert_tags:
            tasks.append(CareerPathTask(
                career_path_id=path_id,
                stage_label="持续",
                category="证书",
                title=f"考取{job.name}相关证书：{', '.join(cert_tags[:2])}",
                description=f"建议考取 {', '.join(cert_tags[:2])} 证书，增强岗位竞争力。",
                due_hint="建议 6 个月内完成",
                priority=3,
                weekly_tasks=[f"复习 {cert} 知识点" for cert in cert_tags[:2]],
                related_skills=cert_tags[:3],
                difficulty_level="中",
            ))

        return tasks

    def _build_overview(self, job, vertical_path: list[dict]) -> str:
        path_names = " -> ".join(item.get("job_name", "") for item in vertical_path)
        return f"围绕 {job.name} 岗位，建议沿以下路径持续推进：{path_names}。系统已拆解阶段任务，建议按周检查进度。"

    def _build_summary(self, job, skill_gaps: list, vertical_path: list[dict]) -> str:
        gap_text = f"当前需重点补齐 {len(skill_gaps)} 项核心技能：{', '.join(skill_gaps[:5])}。" if skill_gaps else "核心技能基础较好，建议持续深化。"
        return f"目标岗位 {job.name}，共 {len(vertical_path)} 个晋升阶段。{gap_text}"

    def _serialize_path(self, career_path: CareerPath, job: Job = None) -> dict[str, Any]:
        data = to_dict(career_path, include=["tasks"])
        data["target_job_name"] = job.name if job else None
        data["target_job_id"] = job.id if job else career_path.target_job_id
        data["vertical_path"] = []
        if job and isinstance(job.job_profile, dict) and job.job_profile.get("vertical_path"):
            data["vertical_path"] = job.job_profile["vertical_path"]
        data["transfer_paths"] = []
        if job and isinstance(job.job_profile, dict) and job.job_profile.get("transfer_paths"):
            data["transfer_paths"] = job.job_profile["transfer_paths"]
        return data

    def get_progress_summary(self, student_id: int) -> dict[str, Any]:
        career_path = (
            self.db.query(CareerPath)
            .filter(CareerPath.student_id == student_id, CareerPath.deleted.is_(False), CareerPath.status == "active")
            .order_by(CareerPath.id.desc())
            .first()
        )
        if not career_path:
            return {"total": 0, "completed": 0, "completion_rate": 0, "tasks_by_category": {}, "tasks_by_priority": {}}

        tasks = self.db.query(CareerPathTask).filter(CareerPathTask.career_path_id == career_path.id).all()
        total = len(tasks)
        completed = sum(1 for t in tasks if t.is_completed)
        rate = round(completed / total * 100, 1) if total else 0

        by_category: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        for t in tasks:
            cat = t.category or "其他"
            by_category[cat] = by_category.get(cat, 0) + 1
            p = str(t.priority or 3)
            by_priority[p] = by_priority.get(p, 0) + 1

        return {
            "career_path_id": career_path.id,
            "target_job_id": career_path.target_job_id,
            "total": total,
            "completed": completed,
            "completion_rate": rate,
            "tasks_by_category": by_category,
            "tasks_by_priority": by_priority,
            "created_at": str(career_path.created_at) if career_path.created_at else None,
            "updated_at": str(career_path.updated_at) if career_path.updated_at else None,
        }

    def complete_task(self, student_id: int, task_id: int) -> dict[str, Any]:
        career_path = (
            self.db.query(CareerPath)
            .filter(CareerPath.student_id == student_id, CareerPath.deleted.is_(False))
            .order_by(CareerPath.id.desc())
            .first()
        )
        if not career_path:
            raise ValueError("当前没有有效的职业路径")

        task = (
            self.db.query(CareerPathTask)
            .filter(CareerPathTask.id == task_id, CareerPathTask.career_path_id == career_path.id)
            .first()
        )
        if not task:
            raise ValueError("任务不存在或不属于当前路径")

        task.is_completed = True
        self.db.commit()
        return self.get_progress_summary(student_id)

    def re_evaluate_path(self, student_id: int) -> dict[str, Any]:
        career_path = (
            self.db.query(CareerPath)
            .filter(CareerPath.student_id == student_id, CareerPath.deleted.is_(False), CareerPath.status == "active")
            .order_by(CareerPath.id.desc())
            .first()
        )
        if not career_path:
            raise ValueError("当前没有有效的职业路径")

        old_path_data = self._serialize_path(career_path)
        old_task_count = len(career_path.tasks) if career_path.tasks else 0

        new_path_data = self.generate_path(student_id, career_path.target_job_id)
        new_task_count = len(new_path_data.get("tasks", []))

        return {
            "old_task_count": old_task_count,
            "new_task_count": new_task_count,
            "path": new_path_data,
            "message": f"路径已重新评估，原任务数 {old_task_count}，新任务数 {new_task_count}。",
        }
