from functools import lru_cache
from pathlib import Path
from tempfile import gettempdir

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_DIR = Path(gettempdir()) / "career-agent"
DEFAULT_SQLITE_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "大学生职业规划 AI 智能体系统"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = "career-agent-secret-key-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    DATABASE_URL: str = f"sqlite:///{(DEFAULT_SQLITE_DIR / 'career_agent_local.db').as_posix()}"
    UPLOAD_DIR: str = "uploads"
    PDF_DIR: str = "uploads/reports"

    # Use a real provider path by default; mock remains configurable via env.
    LLM_PROVIDER: str = "qwen"
    LLM_TEMPERATURE: float = 0.2
    LANGCHAIN_MODEL: str = "qwen-plus"
    LANGCHAIN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DASHSCOPE_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4.1-mini"
    FILE_AGENT_API_KEY: str = ""
    FILE_AGENT_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    FILE_AGENT_MODULE_NAME: str = "qwen3.5-omni-plus-2026-03-15"
    SUPERVISOR_AGENT_API_KEY: str = ""
    SUPERVISOR_AGENT_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    SUPERVISOR_AGENT_MODULE_NAME: str = "qwen3.5-omni-plus-2026-03-15"
    UX_AGENT_API_KEY: str = ""
    UX_AGENT_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    UX_AGENT_MODULE_NAME: str = "qwen3.5-omni-plus-2026-03-15"
    JOB_PACKAGE_AGENT_API_KEY: str = ""
    JOB_PACKAGE_AGENT_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    JOB_PACKAGE_AGENT_MODULE_NAME: str = "qwen3.5-omni-plus-2026-03-15"
    RECRUITMENT_AGENT_API_KEY: str = ""
    RECRUITMENT_AGENT_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    RECRUITMENT_AGENT_MODULE_NAME: str = "qwen3.5-omni-plus-2026-03-15"
    DYNAMIC_PROFILE_AGENT_API_KEY: str = ""
    DYNAMIC_PROFILE_AGENT_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DYNAMIC_PROFILE_AGENT_MODULE_NAME: str = "qwen3.5-omni-plus-2026-03-15"
    AI_INTERVIEW_COACH_AGENT_API_KEY: str = ""
    AI_INTERVIEW_COACH_AGENT_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    AI_INTERVIEW_COACH_AGENT_MODULE_NAME: str = "qwen3.5-omni-plus-2026-03-15"
    CHAT_AGENT_API_KEY: str = ""
    CHAT_AGENT_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    CHAT_AGENT_MODULE_NAME: str = "qwen-plus"
    CODE_AGENT_API_KEY: str = ""
    CODE_AGENT_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    CODE_AGENT_MODULE_NAME: str = "qwen-plus"
    STUDENT_GROWTH_AGENT_API_KEY: str = ""
    STUDENT_GROWTH_AGENT_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    STUDENT_GROWTH_AGENT_MODULE_NAME: str = "qwen-plus"
    MATCH_OPTIMIZATION_AGENT_API_KEY: str = ""
    MATCH_OPTIMIZATION_AGENT_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    MATCH_OPTIMIZATION_AGENT_MODULE_NAME: str = "qwen-plus"
    KNOWLEDGE_GRAPH_AGENT_API_KEY: str = ""
    KNOWLEDGE_GRAPH_AGENT_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    KNOWLEDGE_GRAPH_AGENT_MODULE_NAME: str = "qwen-plus"
    GOVERNANCE_AGENT_API_KEY: str = ""
    GOVERNANCE_AGENT_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    GOVERNANCE_AGENT_MODULE_NAME: str = "qwen-plus"
    DEMO_GUIDANCE_AGENT_API_KEY: str = ""
    DEMO_GUIDANCE_AGENT_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DEMO_GUIDANCE_AGENT_MODULE_NAME: str = "qwen-plus"
    IMAGE_GENERATOR_AGENT_API_KEY: str = ""
    IMAGE_GENERATOR_AGENT_BASE_URL: str = ""
    IMAGE_GENERATOR_AGENT_MODULE_NAME: str = ""

    RESUME_VISION_MODEL: str = "qwen-vl-plus"
    RESUME_OCR_LANG: str = "chi_sim+eng"
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])

    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    NEO4J_DATABASE: str = "neo4j"

    SUPERVISOR_REPORT_STRICT: bool = True
    SUPERVISOR_DYNAMIC_DISPATCH: bool = True
    SUPERVISOR_DYNAMIC_MAX_STEPS: int = 6
    SUPERVISOR_DYNAMIC_REPLAN_LIMIT: int = 1
    SUPERVISOR_DYNAMIC_PLAN_TIMEOUT_SECONDS: int = 18
    FLOWCHART_AGENT_SPLIT_V2: bool = True
    LLM_REQUEST_TIMEOUT_SECONDS: int = 25
    FILE_AGENT_REQUEST_TIMEOUT_SECONDS: int = 25
    FILE_AGENT_MAX_RETRIES: int = 0
    FILE_AGENT_TRANSIENT_NETWORK_MAX_RETRIES: int = 1
    FILE_AGENT_BACKGROUND_REQUEST_TIMEOUT_SECONDS: int = 180
    FILE_AGENT_BACKGROUND_MAX_RETRIES: int = 0
    ASSISTANT_BACKGROUND_MAX_WORKERS: int = 2
    ENABLE_ASSISTANT_TOOL_CARDS: bool = True
    FILE_AGENT_DOCUMENT_SPEC_TIMEOUT_SECONDS: int = 90
    FILE_AGENT_DOCUMENT_SPEC_RETRY_COUNT: int = 1
    ENABLE_BUSINESS_AGENT_LLM_SUMMARY: bool = False
    LLM_RETRY_MAX_ATTEMPTS: int = 3
    LLM_RETRY_INITIAL_DELAY_SECONDS: float = 1.0
    LLM_RETRY_BACKOFF_MULTIPLIER: float = 2.0
    LLM_RETRY_MAX_DELAY_SECONDS: float = 30.0
    AGENT_STRICT_MODE: bool = True

    # HuggingFace 模型配置
    ENABLE_INTENT_EMBEDDING: bool = True
    ENABLE_RAG_RERANKER: bool = True
    HF_MODEL_AUTO_DOWNLOAD: bool = True
    HF_MODEL_LOCAL_FILES_ONLY: bool = False
    HF_HUB_OFFLINE: bool = False
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    EMBEDDING_MODEL_DIR: str = "./models/embedding"
    RERANKER_MODEL_DIR: str = "./models/reranker"
    HF_TOKEN: str = ""
    MODEL_DOWNLOAD_TIMEOUT: int = 120

    @property
    def upload_path(self) -> Path:
        return (BASE_DIR / self.UPLOAD_DIR).resolve()

    @property
    def pdf_path(self) -> Path:
        return (BASE_DIR / self.PDF_DIR).resolve()


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    settings.pdf_path.mkdir(parents=True, exist_ok=True)
    return settings
