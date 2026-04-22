from __future__ import annotations

from typing import Any

from sqlalchemy.orm import joinedload

from app.core.database import SessionLocal
from app.models.job import Job
from app.services.graph.neo4j_service import get_neo4j_service, Neo4jService
from app.services.graph.job_graph_neo4j import JobGraphNeo4jService
from app.services.vector_search_service import VectorSearchService


class JobGraphApiService:
    def __init__(self, neo4j_service: Neo4jService | None = None):
        self.graph = neo4j_service or get_neo4j_service()
        self.job_graph = JobGraphNeo4jService(self.graph)
        self.vector_service = VectorSearchService()

    def get_job_graph_data(
        self,
        enterprise_id: int | None = None,
        category: str | None = None,
        limit: int = 100
    ) -> dict[str, Any]:
        try:
            has_graph_data = self.check_has_data()
        except Exception:
            has_graph_data = False

        if has_graph_data:
            try:
                nodes = self._get_all_job_nodes(enterprise_id, category, limit)
                edges = self._get_all_job_relations(enterprise_id)
                if nodes:
                    categories = set(n.get("category", "") for n in nodes if n.get("category"))
                    companies = set(n.get("company_name", "") for n in nodes if n.get("company_name"))
                    return {
                        "nodes": nodes,
                        "edges": edges,
                        "stats": {
                            "job_count": len(nodes),
                            "relation_count": len(edges),
                            "category_count": len(categories),
                            "company_count": len(companies),
                        },
                        "source": "neo4j",
                    }
            except Exception:
                pass

        database_graph = self._build_graph_from_database(category, limit)
        if database_graph["nodes"]:
            return database_graph

        return self._build_graph_from_milvus(enterprise_id, category, limit)

    def _build_graph_from_database(self, category: str | None = None, limit: int = 100) -> dict[str, Any]:
        with SessionLocal() as db:
            query = (
                db.query(Job)
                .options(joinedload(Job.skills), joinedload(Job.certificates))
                .filter(Job.deleted.is_(False))
                .order_by(Job.id.asc())
            )
            if category:
                query = query.filter(Job.category == category)
            jobs = query.limit(max(1, int(limit or 100))).all()

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        node_ids: set[Any] = set()
        edge_keys: set[tuple[str, str, str]] = set()
        name_to_id = {job.name: job.id for job in jobs}

        def add_node(node: dict[str, Any]) -> None:
            node_id = node.get("id")
            if node_id in node_ids:
                return
            node_ids.add(node_id)
            nodes.append(node)

        def add_edge(source: Any, target: Any, relation_type: str, label: str, weight: float = 0.8, reason: str = "") -> None:
            if source == target:
                return
            key = (str(source), str(target), relation_type)
            if key in edge_keys:
                return
            edge_keys.add(key)
            edges.append(
                {
                    "source": source,
                    "target": target,
                    "relation_type": relation_type,
                    "relation_label": label,
                    "weight": weight,
                    "shared_skill": reason,
                }
            )

        for job in jobs:
            profile = job.job_profile if isinstance(job.job_profile, dict) else {}
            company_name = profile.get("company_name") or (profile.get("source_companies") or ["平台岗位库"])[0] or "平台岗位库"
            add_node(
                {
                    "id": job.id,
                    "label": job.name,
                    "category": job.category or profile.get("category") or "未分类",
                    "company_name": company_name,
                    "enterprise_id": None,
                    "salary_range": job.salary_range or "面议",
                    "location": "未标注",
                    "description": job.description or profile.get("summary") or "",
                }
            )

        for job in jobs:
            profile = job.job_profile if isinstance(job.job_profile, dict) else {}
            previous_id: Any = job.id
            for index, path_item in enumerate(profile.get("vertical_path") or []):
                target_name = str(path_item.get("job_name") or "").strip()
                if not target_name:
                    continue
                target_id: Any = name_to_id.get(target_name)
                if not target_id:
                    target_id = f"vertical:{job.id}:{index}"
                    add_node(
                        {
                            "id": target_id,
                            "label": target_name,
                            "category": job.category or profile.get("category") or "晋升路径",
                            "company_name": "职业路径",
                            "enterprise_id": None,
                            "salary_range": "随级别提升",
                            "location": "职业发展",
                            "description": path_item.get("description") or path_item.get("path_note") or "",
                        }
                    )
                add_edge(
                    previous_id,
                    target_id,
                    "垂直晋升",
                    path_item.get("promotion_condition") or "晋升路径",
                    0.9,
                    path_item.get("path_note") or "",
                )
                previous_id = target_id

            for index, transfer_item in enumerate(profile.get("transfer_paths") or []):
                target_name = str(transfer_item.get("target_job_name") or "").strip()
                if not target_name:
                    continue
                target_id = name_to_id.get(target_name)
                if not target_id:
                    target_id = f"transfer:{job.id}:{index}"
                    add_node(
                        {
                            "id": target_id,
                            "label": target_name,
                            "category": "换岗路径",
                            "company_name": "职业路径",
                            "enterprise_id": None,
                            "salary_range": "视岗位而定",
                            "location": "职业转换",
                            "description": transfer_item.get("path_note") or "",
                        }
                    )
                add_edge(
                    job.id,
                    target_id,
                    "换岗路径",
                    transfer_item.get("path_note") or "换岗路径",
                    0.75,
                    " / ".join(transfer_item.get("required_skills") or []),
                )

        categories = set(n.get("category", "") for n in nodes if n.get("category"))
        companies = set(n.get("company_name", "") for n in nodes if n.get("company_name"))
        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "job_count": len(nodes),
                "relation_count": len(edges),
                "category_count": len(categories),
                "company_count": len(companies),
            },
            "source": "database",
        }

    def _build_graph_from_milvus(
        self,
        enterprise_id: int | None = None,
        category: str | None = None,
        limit: int = 100
    ) -> dict[str, Any]:
        docs = self.vector_service.list_documents(limit=limit)

        if not docs:
            return {
                "nodes": [],
                "edges": [],
                "stats": {"job_count": 0, "relation_count": 0, "category_count": 0, "company_count": 0},
                "source": "milvus_empty",
            }

        nodes = []
        node_map = {}
        for doc in docs:
            doc_id = str(doc.get("id", ""))
            job_id = self._extract_job_id(doc_id)
            if not job_id:
                job_id = hash(doc_id) % 100000

            name = doc.get("job_name", "") or doc.get("title", "") or doc.get("name", "未知岗位")
            job_category = doc.get("category", "") or doc.get("job_category", "") or "未分类"
            company_name = doc.get("company_name", "") or doc.get("enterprise_name", "") or "未知企业"

            if enterprise_id:
                doc_enterprise_id = doc.get("enterprise_id") or doc.get("company_id")
                if doc_enterprise_id and doc_enterprise_id != enterprise_id:
                    continue

            if category and job_category != category:
                continue

            node = {
                "id": job_id,
                "label": name,
                "category": job_category,
                "company_name": company_name,
                "enterprise_id": doc.get("enterprise_id") or doc.get("company_id"),
                "salary_range": doc.get("salary_range", "面议") or "面议",
                "location": doc.get("location", "未知") or "未知",
                "description": doc.get("description", "") or "",
            }
            nodes.append(node)
            node_map[job_id] = node

        edges = self._infer_relations_from_docs(docs, node_map)

        categories = set(n.get("category", "") for n in nodes if n.get("category"))
        companies = set(n.get("company_name", "") for n in nodes if n.get("company_name"))

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "job_count": len(nodes),
                "relation_count": len(edges),
                "category_count": len(categories),
                "company_count": len(companies),
            },
            "source": "milvus",
        }

    def _extract_job_id(self, doc_id: str) -> int | None:
        try:
            parts = doc_id.split("_")
            for part in parts:
                if part.isdigit():
                    return int(part)
            return None
        except Exception:
            return None

    def _infer_relations_from_docs(self, docs: list, node_map: dict) -> list[dict[str, Any]]:
        edges = []
        added_relations = set()

        skills_map = {}
        for doc in docs:
            doc_id = str(doc.get("id", ""))
            job_id = self._extract_job_id(doc_id) or hash(doc_id) % 100000
            skills = doc.get("skills", "") or doc.get("required_skills", "") or ""
            if isinstance(skills, str):
                skills = [s.strip() for s in skills.split(",") if s.strip()]
            for skill in skills:
                if skill not in skills_map:
                    skills_map[skill] = []
                skills_map[skill].append(job_id)

        for skill, job_ids in skills_map.items():
            if len(job_ids) > 1:
                for i in range(len(job_ids)):
                    for j in range(i + 1, len(job_ids)):
                        id1, id2 = job_ids[i], job_ids[j]
                        if id1 in node_map and id2 in node_map:
                            edge_key = (min(id1, id2), max(id1, id2), "技能关联")
                            if edge_key not in added_relations:
                                added_relations.add(edge_key)
                                edges.append({
                                    "source": id1,
                                    "target": id2,
                                    "relation_type": "技能关联",
                                    "relation_label": f"共同技能: {skill}",
                                    "weight": 0.8,
                                    "shared_skill": skill,
                                })

        category_groups = {}
        for node in node_map.values():
            cat = node.get("category", "")
            if cat not in category_groups:
                category_groups[cat] = []
            category_groups[cat].append(node["id"])

        for cat, job_ids in category_groups.items():
            if len(job_ids) > 1 and cat != "未分类":
                for i in range(len(job_ids)):
                    for j in range(i + 1, len(job_ids)):
                        id1, id2 = job_ids[i], job_ids[j]
                        edge_key = (min(id1, id2), max(id1, id2), "同类型")
                        if edge_key not in added_relations:
                            added_relations.add(edge_key)
                            edges.append({
                                "source": id1,
                                "target": id2,
                                "relation_type": "同类型",
                                "relation_label": f"同岗位类型: {cat}",
                                "weight": 0.5,
                            })

        company_groups = {}
        for node in node_map.values():
            company = node.get("company_name", "")
            if company and company != "未知企业":
                if company not in company_groups:
                    company_groups[company] = []
                company_groups[company].append(node["id"])

        for company, job_ids in company_groups.items():
            if len(job_ids) > 1:
                for i in range(len(job_ids)):
                    for j in range(i + 1, len(job_ids)):
                        id1, id2 = job_ids[i], job_ids[j]
                        edge_key = (min(id1, id2), max(id1, id2), "同企业")
                        if edge_key not in added_relations:
                            added_relations.add(edge_key)
                            edges.append({
                                "source": id1,
                                "target": id2,
                                "relation_type": "同企业",
                                "relation_label": f"同企业: {company}",
                                "weight": 0.9,
                                "company_name": company,
                            })

        return edges

    def _get_all_job_nodes(
        self,
        enterprise_id: int | None = None,
        category: str | None = None,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        if enterprise_id:
            cypher = """
            MATCH (e:Enterprise {enterprise_id: $enterprise_id})<-[:BELONGS_TO]-(j:Job)
            RETURN j.job_id AS id,
                   j.name AS label,
                   j.category AS category,
                   j.salary_range AS salary_range,
                   j.location AS location,
                   j.description AS description,
                   e.name AS company_name,
                   e.enterprise_id AS enterprise_id
            LIMIT $limit
            """
            results = self.graph.execute_query(cypher, {"enterprise_id": enterprise_id, "limit": limit})
            if not results:
                cypher = """
                MATCH (j:Job)
                WHERE j.enterprise_id = $enterprise_id
                RETURN j.job_id AS id,
                       j.name AS label,
                       j.category AS category,
                       j.salary_range AS salary_range,
                       j.location AS location,
                       j.description AS description,
                       j.company_name AS company_name,
                       j.enterprise_id AS enterprise_id
                LIMIT $limit
                """
                results = self.graph.execute_query(cypher, {"enterprise_id": enterprise_id, "limit": limit})
        elif category:
            cypher = """
            MATCH (j:Job)
            OPTIONAL MATCH (e:Enterprise)<-[:BELONGS_TO]-(j)
            WHERE j.category = $category
            RETURN j.job_id AS id,
                   j.name AS label,
                   j.category AS category,
                   j.salary_range AS salary_range,
                   j.location AS location,
                   j.description AS description,
                   e.name AS company_name,
                   e.enterprise_id AS enterprise_id
            LIMIT $limit
            """
            results = self.graph.execute_query(cypher, {"category": category, "limit": limit})
        else:
            cypher = """
            MATCH (j:Job)
            OPTIONAL MATCH (e:Enterprise)<-[:BELONGS_TO]-(j)
            RETURN j.job_id AS id,
                   j.name AS label,
                   j.category AS category,
                   j.salary_range AS salary_range,
                   j.location AS location,
                   j.description AS description,
                   e.name AS company_name,
                   e.enterprise_id AS enterprise_id
            LIMIT $limit
            """
            results = self.graph.execute_query(cypher, {"limit": limit})

        for node in results:
            node["category"] = node.get("category") or "未分类"
            node["salary_range"] = node.get("salary_range") or "面议"
            node["location"] = node.get("location") or "未知"
            node["description"] = node.get("description") or ""
            node["company_name"] = node.get("company_name") or "未知企业"

        return results

    def _get_all_job_relations(self, enterprise_id: int | None = None) -> list[dict[str, Any]]:
        if enterprise_id:
            cypher = """
            MATCH (a:Job)-[r:JOB_RELATES]->(b:Job)
            WHERE a.enterprise_id = $enterprise_id OR b.enterprise_id = $enterprise_id
            RETURN a.job_id AS source,
                   b.job_id AS target,
                   r.type AS relation_type,
                   r.weight AS weight
            """
            results = self.graph.execute_query(cypher, {"enterprise_id": enterprise_id})
        else:
            cypher = """
            MATCH (a:Job)-[r:JOB_RELATES]->(b:Job)
            RETURN a.job_id AS source,
                   b.job_id AS target,
                   r.type AS relation_type,
                   r.weight AS weight
            """
            results = self.graph.execute_query(cypher)

        relation_labels = {
            "skill": "技能关联",
            "workflow": "业务流程关联",
            "similar": "相似岗位",
            "related": "相关",
            "promotion": "晋升关联",
            "lateral": "横向调动关联",
        }

        for edge in results:
            rel_type = edge.get("relation_type") or "相关"
            edge["relation_type"] = rel_type
            edge["relation_label"] = relation_labels.get(rel_type.lower(), rel_type)
            edge["weight"] = edge.get("weight") or 1.0

        return results

    def get_job_detail(self, job_id: int) -> dict[str, Any] | None:
        cypher = """
        MATCH (j:Job {job_id: $job_id})
        OPTIONAL MATCH (e:Enterprise)<-[:BELONGS_TO]-(j)
        OPTIONAL MATCH (j)-[r:JOB_RELATES]->(related:Job)
        OPTIONAL MATCH (skill:Skill)-[rs:REQUIRES]->(j)
        RETURN j.job_id AS id,
               j.name AS label,
               j.category AS category,
               j.salary_range AS salary_range,
               j.location AS location,
               j.description AS description,
               e.name AS company_name,
               e.enterprise_id AS enterprise_id,
               collect(DISTINCT {job_id: related.job_id, name: related.name, type: r.type}) AS related_jobs,
               collect(DISTINCT {name: skill.name, level: rs.level}) AS required_skills
        """
        result = self.graph.execute_single(cypher, {"job_id": job_id})
        if not result:
            return None

        result["related_jobs"] = [r for r in result.get("related_jobs", []) if r.get("job_id")]
        result["required_skills"] = [s for s in result.get("required_skills", []) if s.get("name")]
        result["company_name"] = result.get("company_name") or "未知企业"
        return result

    def check_has_data(self) -> bool:
        cypher = "MATCH (j:Job) RETURN count(j) AS count"
        result = self.graph.execute_single(cypher)
        return (result.get("count", 0) if result else 0) > 0


def get_job_graph_api_service() -> JobGraphApiService:
    return JobGraphApiService()
