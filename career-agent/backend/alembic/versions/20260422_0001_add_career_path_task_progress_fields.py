"""add career path task progress fields

Revision ID: 20260422_0001
Revises:
Create Date: 2026-04-22 09:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260422_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    table_name = "career_path_tasks"
    if not _has_table(table_name):
        return

    dialect = op.get_bind().dialect.name

    if not _has_column(table_name, "related_skills"):
        op.add_column(
            table_name,
            sa.Column(
                "related_skills",
                sa.JSON(),
                nullable=True,
                server_default=sa.text("'[]'") if dialect != "mysql" else None,
            ),
        )
        if dialect == "mysql":
            op.execute("UPDATE career_path_tasks SET related_skills = JSON_ARRAY() WHERE related_skills IS NULL")

    if not _has_column(table_name, "difficulty_level"):
        op.add_column(
            table_name,
            sa.Column("difficulty_level", sa.String(length=20), nullable=True, server_default="中"),
        )

    if not _has_column(table_name, "is_completed"):
        op.add_column(
            table_name,
            sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )


def downgrade() -> None:
    table_name = "career_path_tasks"
    if not _has_table(table_name):
        return

    for column_name in ("is_completed", "difficulty_level", "related_skills"):
        if _has_column(table_name, column_name):
            op.drop_column(table_name, column_name)
