import logging
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.base import Base


settings = get_settings()
is_sqlite = settings.DATABASE_URL.startswith("sqlite")
logger = logging.getLogger(__name__)
BACKEND_DIR = Path(__file__).resolve().parents[2]

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if is_sqlite else {},
    future=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _rename_review_enterprise_column() -> None:
    with engine.begin() as conn:
        inspector = inspect(conn)
        if "review_records" not in inspector.get_table_names():
            return

        columns = {column["name"] for column in inspector.get_columns("review_records")}
        if "enterprise_id" in columns or "teacher_id" not in columns:
            return

        dialect = conn.dialect.name
        if dialect == "mysql":
            conn.execute(text("ALTER TABLE review_records CHANGE COLUMN teacher_id enterprise_id BIGINT NOT NULL"))
        elif dialect == "sqlite":
            conn.execute(text("ALTER TABLE review_records RENAME COLUMN teacher_id TO enterprise_id"))


def _clear_legacy_teacher_links() -> None:
    with engine.begin() as conn:
        inspector = inspect(conn)
        tables = set(inspector.get_table_names())

        if "classes" in tables:
            class_columns = {column["name"] for column in inspector.get_columns("classes")}
            if "teacher_id" in class_columns:
                conn.execute(text("UPDATE classes SET teacher_id = NULL WHERE teacher_id IS NOT NULL"))

        legacy_role_ids: list[int] = []
        if "roles" in tables:
            role_columns = {column["name"] for column in inspector.get_columns("roles")}
            if {"id", "code", "name", "description", "deleted"}.issubset(role_columns):
                rows = conn.execute(text("SELECT id FROM roles WHERE code = 'teacher' OR code LIKE 'legacy_teacher_%'"))
                legacy_role_ids = [int(row[0]) for row in rows]
                conn.execute(
                    text(
                        "UPDATE roles "
                        "SET name = '历史角色', description = '教师端已迁移为企业端', deleted = 1 "
                        "WHERE code = 'teacher' OR code LIKE 'legacy_teacher_%'"
                    )
                )
                conn.execute(
                    text(
                        "UPDATE roles "
                        "SET code = CONCAT('legacy_teacher_', id) "
                        "WHERE code = 'teacher'"
                    )
                    if conn.dialect.name == "mysql"
                    else text(
                        "UPDATE roles "
                        "SET code = 'legacy_teacher_' || id "
                        "WHERE code = 'teacher'"
                    )
                )

        if "users" in tables:
            user_columns = {column["name"] for column in inspector.get_columns("users")}
            if {"username", "deleted", "is_active"}.issubset(user_columns):
                conn.execute(text("UPDATE users SET deleted = 1, is_active = 0 WHERE username LIKE 'teacher%'"))
            if legacy_role_ids and {"role_id", "deleted", "is_active"}.issubset(user_columns):
                ids = ", ".join(str(item) for item in legacy_role_ids)
                conn.execute(text(f"UPDATE users SET deleted = 1, is_active = 0 WHERE role_id IN ({ids})"))


def _table_has_column(conn, table_name: str, column_name: str) -> bool:
    inspector = inspect(conn)
    if table_name not in inspector.get_table_names():
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _safe_add_column(conn, table_name: str, column_name: str, sqlite_sql: str, mysql_sql: str) -> None:
    if _table_has_column(conn, table_name, column_name):
        return
    if conn.dialect.name == "mysql":
        conn.execute(text(mysql_sql))
        return
    conn.execute(text(sqlite_sql))


def _safe_create_index(conn, table_name: str, index_name: str, columns: list[str]) -> None:
    inspector = inspect(conn)
    if table_name not in inspector.get_table_names():
        return
    existing = {index["name"] for index in inspector.get_indexes(table_name)}
    if index_name in existing:
        return
    column_sql = ", ".join(columns)
    conn.execute(text(f"CREATE INDEX {index_name} ON {table_name} ({column_sql})"))


def _ensure_career_path_task_columns() -> None:
    with engine.begin() as conn:
        _safe_add_column(
            conn,
            "career_path_tasks",
            "related_skills",
            "ALTER TABLE career_path_tasks ADD COLUMN related_skills JSON DEFAULT '[]'",
            "ALTER TABLE career_path_tasks ADD COLUMN related_skills JSON NULL",
        )
        if conn.dialect.name == "mysql" and _table_has_column(conn, "career_path_tasks", "related_skills"):
            conn.execute(text("UPDATE career_path_tasks SET related_skills = JSON_ARRAY() WHERE related_skills IS NULL"))

        _safe_add_column(
            conn,
            "career_path_tasks",
            "difficulty_level",
            "ALTER TABLE career_path_tasks ADD COLUMN difficulty_level VARCHAR(20) DEFAULT '中'",
            "ALTER TABLE career_path_tasks ADD COLUMN difficulty_level VARCHAR(20) NULL DEFAULT '中'",
        )
        _safe_add_column(
            conn,
            "career_path_tasks",
            "is_completed",
            "ALTER TABLE career_path_tasks ADD COLUMN is_completed BOOLEAN DEFAULT 0 NOT NULL",
            "ALTER TABLE career_path_tasks ADD COLUMN is_completed TINYINT(1) NOT NULL DEFAULT 0",
        )


def _run_schema_migrations() -> None:
    alembic_ini = BACKEND_DIR / "alembic.ini"
    if not alembic_ini.exists():
        _ensure_career_path_task_columns()
        return

    try:
        from alembic import command
        from alembic.config import Config
    except ModuleNotFoundError as exc:
        if exc.name != "alembic":
            raise
        logger.warning("Alembic is not installed; applying compatibility schema migrations only.")
        _ensure_career_path_task_columns()
        return

    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic").replace("\\", "/"))
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))
    command.upgrade(config, "head")


def _validate_model_columns() -> None:
    missing_columns: dict[str, list[str]] = {}
    with engine.connect() as conn:
        inspector = inspect(conn)
        existing_tables = set(inspector.get_table_names())
        for table in Base.metadata.tables.values():
            if table.name not in existing_tables:
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table.name)}
            missing = [column.name for column in table.columns if column.name not in existing_columns]
            if missing:
                missing_columns[table.name] = missing

    if missing_columns:
        details = "; ".join(
            f"{table}: {', '.join(columns)}" for table, columns in sorted(missing_columns.items())
        )
        raise RuntimeError(
            "Database schema is out of date. Run `python migrate_db.py` or `alembic upgrade head`. "
            f"Missing columns: {details}"
        )


def _ensure_assistant_structured_columns() -> None:
    with engine.begin() as conn:
        _safe_add_column(
            conn,
            "assistant_sessions",
            "state_json",
            "ALTER TABLE assistant_sessions ADD COLUMN state_json JSON DEFAULT '{}'",
            "ALTER TABLE assistant_sessions ADD COLUMN state_json JSON NULL",
        )
        _safe_add_column(
            conn,
            "assistant_messages",
            "tool_steps_json",
            "ALTER TABLE assistant_messages ADD COLUMN tool_steps_json JSON DEFAULT '[]'",
            "ALTER TABLE assistant_messages ADD COLUMN tool_steps_json JSON NULL",
        )
        _safe_add_column(
            conn,
            "assistant_messages",
            "result_cards_json",
            "ALTER TABLE assistant_messages ADD COLUMN result_cards_json JSON DEFAULT '[]'",
            "ALTER TABLE assistant_messages ADD COLUMN result_cards_json JSON NULL",
        )
        _safe_add_column(
            conn,
            "assistant_messages",
            "meta_json",
            "ALTER TABLE assistant_messages ADD COLUMN meta_json JSON DEFAULT '{}'",
            "ALTER TABLE assistant_messages ADD COLUMN meta_json JSON NULL",
        )


def _ensure_assistant_indexes() -> None:
    with engine.begin() as conn:
        _safe_create_index(
            conn,
            "assistant_messages",
            "ix_assistant_messages_session_deleted_created_id",
            ["session_id", "deleted", "created_at", "id"],
        )
        _safe_create_index(
            conn,
            "assistant_sessions",
            "ix_assistant_sessions_user_deleted_updated_id",
            ["user_id", "deleted", "updated_at", "id"],
        )


def _recreate_sqlite_integer_id_tables_if_needed() -> None:
    if not is_sqlite:
        return
    with engine.begin() as conn:
        inspector = inspect(conn)
        table_names = set(inspector.get_table_names())
        repair_order = [
            "assistant_messages",
            "assistant_sessions",
            "resume_deliveries",
            "student_resume_versions",
            "student_resumes",
            "report_versions",
            "llm_request_logs",
            "persona_image_assets",
            "enterprise_profiles",
        ]
        for table_name in repair_order:
            if table_name not in table_names:
                continue
            id_column = next(
                (column for column in inspector.get_columns(table_name) if column["name"] == "id"),
                None,
            )
            row_count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()
            if id_column and str(id_column["type"]).upper() != "INTEGER" and int(row_count or 0) == 0:
                conn.execute(text(f"DROP TABLE {table_name}"))


def _ensure_llm_request_logs_columns() -> None:
    with engine.begin() as conn:
        _safe_add_column(
            conn,
            "llm_request_logs",
            "provider",
            "ALTER TABLE llm_request_logs ADD COLUMN provider VARCHAR(50) DEFAULT 'mock'",
            "ALTER TABLE llm_request_logs ADD COLUMN provider VARCHAR(50) NULL",
        )
        _safe_add_column(
            conn,
            "llm_request_logs",
            "model_name",
            "ALTER TABLE llm_request_logs ADD COLUMN model_name VARCHAR(100) DEFAULT 'mock'",
            "ALTER TABLE llm_request_logs ADD COLUMN model_name VARCHAR(100) NULL",
        )
        _safe_add_column(
            conn,
            "llm_request_logs",
            "scene",
            "ALTER TABLE llm_request_logs ADD COLUMN scene VARCHAR(100) DEFAULT 'assistant_chat'",
            "ALTER TABLE llm_request_logs ADD COLUMN scene VARCHAR(100) NULL",
        )
        _safe_add_column(
            conn,
            "llm_request_logs",
            "user_id",
            "ALTER TABLE llm_request_logs ADD COLUMN user_id BIGINT",
            "ALTER TABLE llm_request_logs ADD COLUMN user_id BIGINT NULL",
        )
        _safe_add_column(
            conn,
            "llm_request_logs",
            "session_id",
            "ALTER TABLE llm_request_logs ADD COLUMN session_id BIGINT",
            "ALTER TABLE llm_request_logs ADD COLUMN session_id BIGINT NULL",
        )
        _safe_add_column(
            conn,
            "llm_request_logs",
            "request_id",
            "ALTER TABLE llm_request_logs ADD COLUMN request_id VARCHAR(100)",
            "ALTER TABLE llm_request_logs ADD COLUMN request_id VARCHAR(100) NULL",
        )
        _safe_add_column(
            conn,
            "llm_request_logs",
            "status",
            "ALTER TABLE llm_request_logs ADD COLUMN status VARCHAR(20) DEFAULT 'success'",
            "ALTER TABLE llm_request_logs ADD COLUMN status VARCHAR(20) NULL",
        )
        _safe_add_column(
            conn,
            "llm_request_logs",
            "latency_ms",
            "ALTER TABLE llm_request_logs ADD COLUMN latency_ms FLOAT",
            "ALTER TABLE llm_request_logs ADD COLUMN latency_ms FLOAT NULL",
        )
        _safe_add_column(
            conn,
            "llm_request_logs",
            "prompt_tokens",
            "ALTER TABLE llm_request_logs ADD COLUMN prompt_tokens INTEGER DEFAULT 0",
            "ALTER TABLE llm_request_logs ADD COLUMN prompt_tokens INTEGER NULL",
        )
        _safe_add_column(
            conn,
            "llm_request_logs",
            "completion_tokens",
            "ALTER TABLE llm_request_logs ADD COLUMN completion_tokens INTEGER DEFAULT 0",
            "ALTER TABLE llm_request_logs ADD COLUMN completion_tokens INTEGER NULL",
        )
        _safe_add_column(
            conn,
            "llm_request_logs",
            "total_tokens",
            "ALTER TABLE llm_request_logs ADD COLUMN total_tokens INTEGER DEFAULT 0",
            "ALTER TABLE llm_request_logs ADD COLUMN total_tokens INTEGER NULL",
        )
        _safe_add_column(
            conn,
            "llm_request_logs",
            "input_chars",
            "ALTER TABLE llm_request_logs ADD COLUMN input_chars INTEGER DEFAULT 0",
            "ALTER TABLE llm_request_logs ADD COLUMN input_chars INTEGER NULL",
        )
        _safe_add_column(
            conn,
            "llm_request_logs",
            "output_chars",
            "ALTER TABLE llm_request_logs ADD COLUMN output_chars INTEGER DEFAULT 0",
            "ALTER TABLE llm_request_logs ADD COLUMN output_chars INTEGER NULL",
        )
        _safe_add_column(
            conn,
            "llm_request_logs",
            "error_message",
            "ALTER TABLE llm_request_logs ADD COLUMN error_message TEXT",
            "ALTER TABLE llm_request_logs ADD COLUMN error_message TEXT NULL",
        )
        _safe_add_column(
            conn,
            "llm_request_logs",
            "raw_usage_json",
            "ALTER TABLE llm_request_logs ADD COLUMN raw_usage_json JSON DEFAULT '{}'",
            "ALTER TABLE llm_request_logs ADD COLUMN raw_usage_json JSON NULL",
        )
        _safe_add_column(
            conn,
            "llm_request_logs",
            "raw_meta_json",
            "ALTER TABLE llm_request_logs ADD COLUMN raw_meta_json JSON DEFAULT '{}'",
            "ALTER TABLE llm_request_logs ADD COLUMN raw_meta_json JSON NULL",
        )


def _ensure_resume_entity_columns() -> None:
    with engine.begin() as conn:
        _safe_add_column(
            conn,
            "resume_deliveries",
            "resume_id",
            "ALTER TABLE resume_deliveries ADD COLUMN resume_id BIGINT",
            "ALTER TABLE resume_deliveries ADD COLUMN resume_id BIGINT NULL",
        )
        _safe_add_column(
            conn,
            "resume_deliveries",
            "resume_version_id",
            "ALTER TABLE resume_deliveries ADD COLUMN resume_version_id BIGINT",
            "ALTER TABLE resume_deliveries ADD COLUMN resume_version_id BIGINT NULL",
        )
        _safe_add_column(
            conn,
            "resume_deliveries",
            "target_job_id",
            "ALTER TABLE resume_deliveries ADD COLUMN target_job_id BIGINT",
            "ALTER TABLE resume_deliveries ADD COLUMN target_job_id BIGINT NULL",
        )

        _safe_add_column(
            conn,
            "student_resumes",
            "student_id",
            "ALTER TABLE student_resumes ADD COLUMN student_id BIGINT",
            "ALTER TABLE student_resumes ADD COLUMN student_id BIGINT NULL",
        )
        _safe_add_column(
            conn,
            "student_resumes",
            "title",
            "ALTER TABLE student_resumes ADD COLUMN title VARCHAR(120)",
            "ALTER TABLE student_resumes ADD COLUMN title VARCHAR(120) NULL",
        )
        _safe_add_column(
            conn,
            "student_resumes",
            "target_job",
            "ALTER TABLE student_resumes ADD COLUMN target_job VARCHAR(120)",
            "ALTER TABLE student_resumes ADD COLUMN target_job VARCHAR(120) NULL",
        )
        _safe_add_column(
            conn,
            "student_resumes",
            "target_industry",
            "ALTER TABLE student_resumes ADD COLUMN target_industry VARCHAR(120)",
            "ALTER TABLE student_resumes ADD COLUMN target_industry VARCHAR(120) NULL",
        )
        _safe_add_column(
            conn,
            "student_resumes",
            "target_city",
            "ALTER TABLE student_resumes ADD COLUMN target_city VARCHAR(120)",
            "ALTER TABLE student_resumes ADD COLUMN target_city VARCHAR(120) NULL",
        )
        _safe_add_column(
            conn,
            "student_resumes",
            "scene_type",
            "ALTER TABLE student_resumes ADD COLUMN scene_type VARCHAR(60)",
            "ALTER TABLE student_resumes ADD COLUMN scene_type VARCHAR(60) NULL",
        )
        _safe_add_column(
            conn,
            "student_resumes",
            "is_default",
            "ALTER TABLE student_resumes ADD COLUMN is_default BOOLEAN DEFAULT 0",
            "ALTER TABLE student_resumes ADD COLUMN is_default TINYINT(1) NULL",
        )
        _safe_add_column(
            conn,
            "student_resumes",
            "status",
            "ALTER TABLE student_resumes ADD COLUMN status VARCHAR(30) DEFAULT 'active'",
            "ALTER TABLE student_resumes ADD COLUMN status VARCHAR(30) NULL",
        )
        _safe_add_column(
            conn,
            "student_resumes",
            "source_attachment_id",
            "ALTER TABLE student_resumes ADD COLUMN source_attachment_id BIGINT",
            "ALTER TABLE student_resumes ADD COLUMN source_attachment_id BIGINT NULL",
        )
        _safe_add_column(
            conn,
            "student_resumes",
            "current_version_id",
            "ALTER TABLE student_resumes ADD COLUMN current_version_id BIGINT",
            "ALTER TABLE student_resumes ADD COLUMN current_version_id BIGINT NULL",
        )
        _safe_add_column(
            conn,
            "student_resumes",
            "summary",
            "ALTER TABLE student_resumes ADD COLUMN summary TEXT",
            "ALTER TABLE student_resumes ADD COLUMN summary TEXT NULL",
        )

        _safe_add_column(
            conn,
            "student_resume_versions",
            "resume_id",
            "ALTER TABLE student_resume_versions ADD COLUMN resume_id BIGINT",
            "ALTER TABLE student_resume_versions ADD COLUMN resume_id BIGINT NULL",
        )
        _safe_add_column(
            conn,
            "student_resume_versions",
            "version_no",
            "ALTER TABLE student_resume_versions ADD COLUMN version_no INTEGER DEFAULT 1",
            "ALTER TABLE student_resume_versions ADD COLUMN version_no INT NULL",
        )
        _safe_add_column(
            conn,
            "student_resume_versions",
            "attachment_id",
            "ALTER TABLE student_resume_versions ADD COLUMN attachment_id BIGINT",
            "ALTER TABLE student_resume_versions ADD COLUMN attachment_id BIGINT NULL",
        )
        _safe_add_column(
            conn,
            "student_resume_versions",
            "parsed_json",
            "ALTER TABLE student_resume_versions ADD COLUMN parsed_json JSON DEFAULT '{}'",
            "ALTER TABLE student_resume_versions ADD COLUMN parsed_json JSON NULL",
        )
        _safe_add_column(
            conn,
            "student_resume_versions",
            "optimized_json",
            "ALTER TABLE student_resume_versions ADD COLUMN optimized_json JSON DEFAULT '{}'",
            "ALTER TABLE student_resume_versions ADD COLUMN optimized_json JSON NULL",
        )
        _safe_add_column(
            conn,
            "student_resume_versions",
            "score_snapshot",
            "ALTER TABLE student_resume_versions ADD COLUMN score_snapshot JSON DEFAULT '{}'",
            "ALTER TABLE student_resume_versions ADD COLUMN score_snapshot JSON NULL",
        )
        _safe_add_column(
            conn,
            "student_resume_versions",
            "change_summary",
            "ALTER TABLE student_resume_versions ADD COLUMN change_summary TEXT",
            "ALTER TABLE student_resume_versions ADD COLUMN change_summary TEXT NULL",
        )
        _safe_add_column(
            conn,
            "student_resume_versions",
            "is_active",
            "ALTER TABLE student_resume_versions ADD COLUMN is_active BOOLEAN DEFAULT 1",
            "ALTER TABLE student_resume_versions ADD COLUMN is_active TINYINT(1) NULL",
        )


def init_db() -> None:
    import app.models.auth  # noqa: F401
    import app.models.career  # noqa: F401
    import app.models.job  # noqa: F401
    import app.models.persona  # noqa: F401
    import app.models.student  # noqa: F401

    _rename_review_enterprise_column()
    _recreate_sqlite_integer_id_tables_if_needed()
    Base.metadata.create_all(bind=engine)
    _run_schema_migrations()
    _ensure_resume_entity_columns()
    _ensure_assistant_structured_columns()
    _ensure_assistant_indexes()
    _ensure_llm_request_logs_columns()
    _clear_legacy_teacher_links()
    _validate_model_columns()
