from __future__ import annotations

from typing import Any

from app.services.graph.neo4j_service import get_neo4j_service, Neo4jService


class GraphAugmenter:
    def __init__(self, neo4j_service: Neo4jService | None = None):
        self.neo4j = neo4j_service or get_neo4j_service()

    def augment_query(self, query: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}
        job_id = context.get("job_id")
        student_id = context.get("student_id")

        results = {
            "query": query,
            "related_jobs": [],
            "related_skills": [],
            "career_paths": [],
        }

        if job_id:
            try:
                related_jobs = self._get_related_jobs(job_id)
                results["related_jobs"] = related_jobs
            except Exception:
                pass

        if student_id:
            try:
                skill_gap = self._get_skill_gap(student_id, job_id)
                results["skill_gap"] = skill_gap
            except Exception:
                pass

        return results

    def _get_related_jobs(self, job_id: int) -> list[dict[str, Any]]:
        cypher = """
        MATCH (j1:Job {job_id: $job_id})-[:JOB_RELATES]->(j2:Job)
        RETURN j2.job_id AS job_id, j2.name AS name, j2.category AS category
        LIMIT 10
        """
        return self.neo4j.execute_query(cypher, {"job_id": job_id})

    def _get_skill_gap(self, student_id: int, job_id: int | None) -> dict[str, Any]:
        if not job_id:
            return {}
        cypher = """
        MATCH (st:Student {student_id: $student_id})
        MATCH (j:Job {job_id: $job_id})
        MATCH (j)-[:REQUIRES]->(s:Skill)
        OPTIONAL MATCH (st)-[r:KNOWS]->(s)
        RETURN s.name AS skill_name, r IS NOT NULL AS possessed
        """
        results = self.neo4j.execute_query(cypher, {"student_id": student_id, "job_id": job_id})
        missing = [r["skill_name"] for r in results if not r.get("possessed")]
        possessed = [r["skill_name"] for r in results if r.get("possessed")]
        return {"missing": missing, "possessed": possessed}

    def get_career_paths(self, job_id: int, max_hops: int = 5) -> list[dict[str, Any]]:
        cypher = f"""
        MATCH path = (j:Job {{job_id: $job_id}})-[:NEXT*1..{max_hops}]->(next_j:Job)
        WITH path, next_j,
             REDUCE(years = 0.0, r IN relationships(path) | years + r.years_required) AS total_years
        RETURN next_j.name AS job_name, total_years, length(path) AS hops
        ORDER BY hops
        LIMIT 10
        """
        return self.neo4j.execute_query(cypher, {"job_id": job_id})


_graph_augmenter: GraphAugmenter | None = None


def get_graph_augmenter() -> GraphAugmenter:
    global _graph_augmenter
    if _graph_augmenter is None:
        _graph_augmenter = GraphAugmenter()
    return _graph_augmenter
