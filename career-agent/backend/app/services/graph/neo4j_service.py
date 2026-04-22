from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any

from neo4j import GraphDatabase, Driver

from app.core.config import get_settings


class Neo4jService:
    _instance: Neo4jService | None = None
    _driver: Driver | None = None

    def __init__(self):
        settings = get_settings()
        self.uri = getattr(settings, "NEO4J_URI", None) or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.username = getattr(settings, "NEO4J_USERNAME", None) or os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = getattr(settings, "NEO4J_PASSWORD", None) or os.getenv("NEO4J_PASSWORD", "password")
        self.database = getattr(settings, "NEO4J_DATABASE", None) or os.getenv("NEO4J_DATABASE", "neo4j")

    @classmethod
    def get_instance(cls) -> Neo4jService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_driver(self) -> Driver:
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password)
            )
        return self._driver

    @contextmanager
    def session(self):
        driver = self.get_driver()
        session = driver.session(database=self.database)
        try:
            yield session
        finally:
            session.close()

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None

    def verify_connectivity(self) -> bool:
        try:
            with self.session() as session:
                result = session.run("RETURN 1 AS test")
                return result.single() is not None
        except Exception:
            return False

    def execute_query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        with self.session() as session:
            result = session.run(cypher, params or {})
            return [dict(record) for record in result]

    def execute_single(self, cypher: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        results = self.execute_query(cypher, params)
        return results[0] if results else None

    def execute_count(self, cypher: str, params: dict[str, Any] | None = None) -> int:
        result = self.execute_single(cypher, params)
        return result.get("count", 0) if result else 0

    def create_node(self, label: str, properties: dict[str, Any]) -> dict[str, Any]:
        props_str = ", ".join([f"{k}: ${k}" for k in properties.keys()])
        cypher = f"CREATE (n:{label} {{{props_str}}}) RETURN n"
        result = self.execute_single(cypher, properties)
        return dict(result.get("n", {})) if result else {}

    def find_node(self, label: str, property_key: str, property_value: Any) -> dict[str, Any] | None:
        cypher = f"MATCH (n:{label} {{{property_key}: ${property_key}}}) RETURN n"
        result = self.execute_single(cypher, {property_key: property_value})
        return dict(result.get("n", {})) if result else None

    def find_nodes(self, label: str, property_key: str, property_value: Any) -> list[dict[str, Any]]:
        cypher = f"MATCH (n:{label} {{{property_key}: ${property_key}}}) RETURN n"
        results = self.execute_query(cypher, {property_key: property_value})
        return [dict(r.get("n", {})) for r in results]

    def create_relationship(
        self,
        from_label: str,
        from_property_key: str,
        from_property_value: Any,
        rel_type: str,
        to_label: str,
        to_property_key: str,
        to_property_value: Any,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        props_clause = ""
        if properties:
            props_str = ", ".join([f"{k}: ${k}" for k in properties.keys()])
            props_clause = f" {{{props_str}}}"

        cypher = f"""
        MATCH (a:{from_label} {{{from_property_key}: $from_value}})
        MATCH (b:{to_label} {{{to_property_key}: $to_value}})
        CREATE (a)-[r:{rel_type}{props_clause}]->(b)
        RETURN count(r) AS created
        """
        params = {
            "from_value": from_property_value,
            "to_value": to_property_value,
        }
        if properties:
            params.update(properties)

        result = self.execute_single(cypher, params)
        return result.get("created", 0) > 0 if result else False

    def delete_all(self, label: str) -> int:
        cypher = f"MATCH (n:{label}) DETACH DELETE n RETURN count(n) AS deleted"
        result = self.execute_single(cypher)
        return result.get("deleted", 0) if result else 0

    def clear_all(self) -> bool:
        try:
            with self.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
            return True
        except Exception:
            return False


def get_neo4j_service() -> Neo4jService:
    return Neo4jService.get_instance()
