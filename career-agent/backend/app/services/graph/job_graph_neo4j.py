from __future__ import annotations

from typing import Any

from app.services.graph.neo4j_service import get_neo4j_service, Neo4jService


class JobGraphNeo4jService:
    def __init__(self, neo4j_service: Neo4jService | None = None):
        self.graph = neo4j_service or get_neo4j_service()

    def create_job_node(self, job_id: int, name: str, properties: dict[str, Any]) -> bool:
        cypher = """
        MERGE (j:Job {job_id: $job_id})
        SET j.name = $name,
            j.category = $category,
            j.salary_range = $salary_range,
            j.location = $location,
            j.description = $description
        RETURN j
        """
        params = {
            "job_id": job_id,
            "name": name,
            "category": properties.get("category", ""),
            "salary_range": properties.get("salary_range", ""),
            "location": properties.get("location", ""),
            "description": properties.get("description", ""),
        }
        result = self.graph.execute_single(cypher, params)
        return result is not None

    def create_job_relation(
        self,
        from_job_id: int,
        to_job_id: int,
        relation_type: str,
        weight: float = 1.0,
    ) -> bool:
        cypher = """
        MATCH (a:Job {job_id: $from_id})
        MATCH (b:Job {job_id: $to_id})
        CREATE (a)-[r:JOB_RELATES {type: $rel_type, weight: $weight}]->(b)
        RETURN count(r) AS created
        """
        params = {
            "from_id": from_job_id,
            "to_id": to_job_id,
            "rel_type": relation_type,
            "weight": weight,
        }
        result = self.graph.execute_single(cypher, params)
        return result.get("created", 0) > 0 if result else False

    def get_related_jobs(self, job_id: int, depth: int = 1) -> list[dict[str, Any]]:
        cypher = f"""
        MATCH path = (j1:Job {{job_id: $job_id}})-[:JOB_RELATES*1..{depth}]->(j2:Job)
        WHERE j1 <> j2
        WITH path, j2, length(path) as hops
        RETURN j2.job_id AS job_id,
               j2.name AS name,
               j2.category AS category,
               hops,
               REDUCE(props = [], r IN relationships(path) | props + {{type: r.type, weight: r.weight}}) AS relations
        ORDER BY hops
        """
        return self.graph.execute_query(cypher, {"job_id": job_id})

    def get_job_paths(self, from_job_id: int, to_job_id: int, max_depth: int = 5) -> list[dict[str, Any]]:
        cypher = f"""
        MATCH path = (a:Job {{job_id: $from_id}})-[:JOB_RELATES*1..{max_depth}]->(b:Job {{job_id: $to_id}})
        WITH path, b, length(path) as hops
        RETURN b.job_id AS job_id,
               b.name AS name,
               hops,
               REDUCE(nodes = [], n IN nodes(path) | nodes + {{job_id: n.job_id, name: n.name}}) AS path_nodes
        ORDER BY hops
        """
        return self.graph.execute_query(cypher, {"from_id": from_job_id, "to_id": to_job_id})

    def get_similar_jobs(self, job_id: int, limit: int = 5) -> list[dict[str, Any]]:
        cypher = """
        MATCH (j1:Job {job_id: $job_id})-[:JOB_RELATES]->(j2:Job)
        WHERE j1 <> j2
        WITH j2, count(*) as common_relations
        ORDER BY common_relations DESC
        LIMIT $limit
        RETURN j2.job_id AS job_id,
               j2.name AS name,
               j2.category AS category,
               common_relations
        """
        return self.graph.execute_query(cypher, {"job_id": job_id, "limit": limit})

    def get_all_jobs(self, category: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if category:
            cypher = """
            MATCH (j:Job)
            WHERE j.category = $category
            RETURN j.job_id AS job_id, j.name AS name, j.category AS category
            ORDER BY j.name
            LIMIT $limit
            """
            return self.graph.execute_query(cypher, {"category": category, "limit": limit})
        else:
            cypher = """
            MATCH (j:Job)
            RETURN j.job_id AS job_id, j.name AS name, j.category AS category
            ORDER BY j.name
            LIMIT $limit
            """
            return self.graph.execute_query(cypher, {"limit": limit})

    def delete_job_node(self, job_id: int) -> bool:
        cypher = """
        MATCH (j:Job {job_id: $job_id})
        DETACH DELETE j
        RETURN count(j) AS deleted
        """
        result = self.graph.execute_single(cypher, {"job_id": job_id})
        return result.get("deleted", 0) > 0 if result else False

    def delete_all_relations(self) -> int:
        cypher = """
        MATCH ()-[r:JOB_RELATES]->()
        DELETE r
        RETURN count(r) AS deleted
        """
        result = self.graph.execute_single(cypher)
        return result.get("deleted", 0) if result else 0


def get_job_graph_neo4j_service() -> JobGraphNeo4jService:
    return JobGraphNeo4jService()
