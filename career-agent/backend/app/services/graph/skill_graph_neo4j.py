from __future__ import annotations

from typing import Any

from app.services.graph.neo4j_service import get_neo4j_service, Neo4jService


class SkillGraphNeo4jService:
    def __init__(self, neo4j_service: Neo4jService | None = None):
        self.graph = neo4j_service or get_neo4j_service()

    def create_skill_node(self, skill_id: int, name: str, category: str, properties: dict[str, Any] | None = None) -> bool:
        cypher = """
        MERGE (s:Skill {skill_id: $skill_id})
        SET s.name = $name,
            s.category = $category,
            s.difficulty = $difficulty,
            s.description = $description
        RETURN s
        """
        props = properties or {}
        params = {
            "skill_id": skill_id,
            "name": name,
            "category": category,
            "difficulty": props.get("difficulty", "intermediate"),
            "description": props.get("description", ""),
        }
        result = self.graph.execute_single(cypher, params)
        return result is not None

    def create_skill_relation(
        self,
        from_skill_id: int,
        to_skill_id: int,
        relation_type: str,
        weight: float = 1.0,
    ) -> bool:
        cypher = """
        MATCH (a:Skill {skill_id: $from_id})
        MATCH (b:Skill {skill_id: $to_id})
        CREATE (a)-[r:SKILL_RELATES {type: $rel_type, weight: $weight}]->(b)
        RETURN count(r) AS created
        """
        params = {
            "from_id": from_skill_id,
            "to_id": to_skill_id,
            "rel_type": relation_type,
            "weight": weight,
        }
        result = self.graph.execute_single(cypher, params)
        return result.get("created", 0) > 0 if result else False

    def create_job_skill_relation(
        self,
        job_id: int,
        skill_id: int,
        importance: float = 1.0,
    ) -> bool:
        cypher = """
        MATCH (j:Job {job_id: $job_id})
        MATCH (s:Skill {skill_id: $skill_id})
        CREATE (j)-[r:REQUIRES {importance: $importance}]->(s)
        RETURN count(r) AS created
        """
        params = {"job_id": job_id, "skill_id": skill_id, "importance": importance}
        result = self.graph.execute_single(cypher, params)
        return result.get("created", 0) > 0 if result else False

    def create_student_skill_relation(
        self,
        student_id: int,
        skill_id: int,
        proficiency: str = "intermediate",
    ) -> bool:
        cypher = """
        MATCH (st:Student {student_id: $student_id})
        MATCH (s:Skill {skill_id: $skill_id})
        CREATE (st)-[r:KNOWS {proficiency: $proficiency}]->(s)
        RETURN count(r) AS created
        """
        params = {"student_id": student_id, "skill_id": skill_id, "proficiency": proficiency}
        result = self.graph.execute_single(cypher, params)
        return result.get("created", 0) > 0 if result else False

    def get_skill_gap(self, student_id: int, job_id: int) -> dict[str, Any]:
        cypher = """
        MATCH (st:Student {student_id: $student_id})
        MATCH (j:Job {job_id: $job_id})
        MATCH (j)-[:REQUIRES]->(s:Skill)
        OPTIONAL MATCH (st)-[r:KNOWS]->(s)
        WITH s, r, j,
             CASE WHEN r IS NULL THEN true ELSE false END AS missing
        RETURN s.skill_id AS skill_id,
               s.name AS skill_name,
               s.category AS category,
               s.difficulty AS difficulty,
               missing,
               r.proficiency AS proficiency
        ORDER BY missing DESC, s.difficulty
        """
        results = self.graph.execute_query(cypher, {"student_id": student_id, "job_id": job_id})

        missing = [r for r in results if r.get("missing")]
        possessed = [r for r in results if not r.get("missing")]

        return {
            "job_id": job_id,
            "student_id": student_id,
            "total_required": len(results),
            "missing_count": len(missing),
            "possessed_count": len(possessed),
            "missing_skills": missing,
            "possessed_skills": possessed,
        }

    def get_learning_path(self, skill_id: int, limit: int = 5) -> list[dict[str, Any]]:
        cypher = f"""
        MATCH path = (s:Skill {{skill_id: $skill_id}})<-[:SKILL_RELATES*1..3]-(prereq:Skill)
        WHERE s <> prereq
        WITH path, prereq, length(path) as hops
        RETURN prereq.skill_id AS skill_id,
               prereq.name AS skill_name,
               prereq.category AS category,
               hops
        ORDER BY hops
        LIMIT $limit
        """
        return self.graph.execute_query(cypher, {"skill_id": skill_id, "limit": limit})

    def get_related_skills(self, skill_id: int, limit: int = 10) -> list[dict[str, Any]]:
        cypher = """
        MATCH (s1:Skill {skill_id: $skill_id})-[r:SKILL_RELATES]->(s2:Skill)
        WHERE s1 <> s2
        WITH s2, r.weight as weight
        ORDER BY weight DESC
        LIMIT $limit
        RETURN s2.skill_id AS skill_id,
               s2.name AS skill_name,
               s2.category AS category,
               weight
        """
        return self.graph.execute_query(cypher, {"skill_id": skill_id, "limit": limit})

    def get_jobs_by_skill(self, skill_id: int, limit: int = 10) -> list[dict[str, Any]]:
        cypher = """
        MATCH (j:Job)-[:REQUIRES]->(s:Skill {skill_id: $skill_id})
        WITH j, count(*) as importance
        ORDER BY importance DESC
        LIMIT $limit
        RETURN j.job_id AS job_id,
               j.name AS job_name,
               j.category AS category,
               importance
        """
        return self.graph.execute_query(cypher, {"skill_id": skill_id, "limit": limit})

    def get_similar_students(self, student_id: int, limit: int = 5) -> list[dict[str, Any]]:
        cypher = """
        MATCH (s1:Student {student_id: $student_id})-[:KNOWS]->(sk:Skill)<-[:KNOWS]-(s2:Student)
        WHERE s1 <> s2
        WITH s2, count(sk) as common_skills
        ORDER BY common_skills DESC
        LIMIT $limit
        RETURN s2.student_id AS student_id,
               s2.name AS name,
               common_skills
        """
        return self.graph.execute_query(cypher, {"student_id": student_id, "limit": limit})

    def delete_skill_node(self, skill_id: int) -> bool:
        cypher = """
        MATCH (s:Skill {skill_id: $skill_id})
        DETACH DELETE s
        RETURN count(s) AS deleted
        """
        result = self.graph.execute_single(cypher, {"skill_id": skill_id})
        return result.get("deleted", 0) > 0 if result else False


def get_skill_graph_neo4j_service() -> SkillGraphNeo4jService:
    return SkillGraphNeo4jService()
