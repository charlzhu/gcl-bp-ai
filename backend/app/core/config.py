import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    app_host: str = "0.0.0.0"
    app_name: str = "gcl-bp-ai"
    app_env: Literal["local", "dev", "test", "prod"] = "local"
    app_debug: bool = True
    app_version: str = "0.1.0"
    app_port: int = 8000
    api_v1_prefix: str = "/api/v1"
    trace_header_name: str = "X-Trace-Id"
    request_id_header_name: str = "X-Request-Id"
    log_level: str = "INFO"
    file_storage_root: Path = Path("data/files")
    log_root: Path = Path("data/logs")
    demo_mode: bool = True
    max_upload_size_mb: int = 20
    allowed_origins: list[str] = Field(default_factory=lambda: ["*"])
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_db: str = "logistics_ai"
    mysql_user: str = "root"
    mysql_password: str = "123456"
    mysql_charset: str = "utf8mb4"
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    milvus_host: str = "127.0.0.1"
    milvus_port: int = 19530
    milvus_user: str = ""
    milvus_password: str = ""
    source_mysql_host: str = "10.76.13.161"
    source_mysql_port: int = 19531
    source_mysql_db: str = "jyjh_db"
    source_mysql_user: str = "jyjhuser_zcc"
    source_mysql_password: str = "jyjh123!"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_guardrail_enabled: bool = False
    llm_guardrail_mode: Literal["off", "shadow", "assist"] = "off"
    llm_guardrail_sample_rate: float = 0.0
    llm_guardrail_min_confidence: float = 0.9
    llm_guardrail_a_querykey_whitelist: list[str] = Field(default_factory=list)
    llm_guardrail_audit_enabled: bool = True
    llm_clarification_assist_enabled: bool = True
    llm_clarification_assist_mode: Literal["off", "shadow", "assist"] = "assist"
    llm_clarification_assist_sample_rate: float = 1.0
    llm_clarification_assist_min_confidence: float = 0.7
    llm_clarification_assist_category_whitelist: list[str] = Field(default_factory=list)
    llm_clarification_assist_audit_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent.parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("llm_guardrail_mode", mode="before")
    @classmethod
    def _normalize_llm_guardrail_mode(cls, value: object) -> object:
        """兼容旧版 disabled 配置，同时把空值统一收敛成 off。"""
        if value is None:
            return "off"
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"", "disabled"}:
                return "off"
            return normalized
        return value

    @field_validator("llm_guardrail_a_querykey_whitelist", mode="before")
    @classmethod
    def _parse_llm_guardrail_a_querykey_whitelist(cls, value: object) -> object:
        """解析 Guardrail A 类白名单。

        说明：
            1. 兼容 JSON 数组和逗号分隔两种写法；
            2. 统一去掉空白和空字符串，避免配置误伤；
            3. 如果未显式配置，则保留空列表，后续走服务默认白名单。
        """
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:  # noqa: BLE001
                    pass
            return [item.strip() for item in raw.split(",") if item.strip()]
        return value

    @field_validator("llm_clarification_assist_mode", mode="before")
    @classmethod
    def _normalize_llm_clarification_assist_mode(cls, value: object) -> object:
        """兼容空值和旧版 disabled 写法。"""
        if value is None:
            return "off"
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"", "disabled"}:
                return "off"
            return normalized
        return value

    @field_validator("llm_clarification_assist_category_whitelist", mode="before")
    @classmethod
    def _parse_llm_clarification_assist_category_whitelist(cls, value: object) -> object:
        """解析澄清辅助允许增强的澄清类别白名单。"""
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:  # noqa: BLE001
                    pass
            return [item.strip() for item in raw.split(",") if item.strip()]
        return value

    def ensure_runtime_dirs(self) -> None:
        self.file_storage_root.mkdir(parents=True, exist_ok=True)
        self.log_root.mkdir(parents=True, exist_ok=True)

    @property
    def mysql_dsn(self) -> str:
        return URL.create(
            drivername="mysql+pymysql",
            username=self.mysql_user,
            password=self.mysql_password,
            host=self.mysql_host,
            port=self.mysql_port,
            database=self.mysql_db,
            query={"charset": self.mysql_charset},
        ).render_as_string(hide_password=False)

    @property
    def source_mysql_dsn(self) -> str:
        return URL.create(
            drivername="mysql+pymysql",
            username=self.source_mysql_user,
            password=self.source_mysql_password,
            host=self.source_mysql_host,
            port=self.source_mysql_port,
            database=self.source_mysql_db,
            query={"charset": self.mysql_charset},
        ).render_as_string(hide_password=False)

    @property
    def resolved_source_mysql_dsn(self) -> str:
        """返回源库连接串，直接使用 .env 中配置的源库账号信息。"""
        return self.source_mysql_dsn

    # Compatibility aliases for the imported skeleton.
    @property
    def APP_HOST(self) -> str:
        return self.app_host

    @property
    def APP_NAME(self) -> str:
        return self.app_name

    @property
    def APP_ENV(self) -> str:
        return self.app_env

    @property
    def APP_DEBUG(self) -> bool:
        return self.app_debug

    @property
    def APP_VERSION(self) -> str:
        return self.app_version

    @property
    def APP_PORT(self) -> int:
        return self.app_port

    @property
    def API_V1_PREFIX(self) -> str:
        return self.api_v1_prefix

    @property
    def TRACE_HEADER_NAME(self) -> str:
        return self.trace_header_name

    @property
    def REQUEST_ID_HEADER_NAME(self) -> str:
        return self.request_id_header_name

    @property
    def LOG_LEVEL(self) -> str:
        return self.log_level

    @property
    def MYSQL_HOST(self) -> str:
        return self.mysql_host

    @property
    def MYSQL_PORT(self) -> int:
        return self.mysql_port

    @property
    def MYSQL_DB(self) -> str:
        return self.mysql_db

    @property
    def MYSQL_USER(self) -> str:
        return self.mysql_user

    @property
    def MYSQL_PASSWORD(self) -> str:
        return self.mysql_password

    @property
    def MYSQL_CHARSET(self) -> str:
        return self.mysql_charset

    @property
    def REDIS_HOST(self) -> str:
        return self.redis_host

    @property
    def REDIS_PORT(self) -> int:
        return self.redis_port

    @property
    def REDIS_DB(self) -> int:
        return self.redis_db

    @property
    def REDIS_PASSWORD(self) -> str:
        return self.redis_password

    @property
    def MILVUS_HOST(self) -> str:
        return self.milvus_host

    @property
    def MILVUS_PORT(self) -> int:
        return self.milvus_port

    @property
    def MILVUS_USER(self) -> str:
        return self.milvus_user

    @property
    def MILVUS_PASSWORD(self) -> str:
        return self.milvus_password

    @property
    def MILVUS_COLLECTION_PREFIX(self) -> str:
        return self.milvus_collection_prefix

    @property
    def SOURCE_MYSQL_HOST(self) -> str:
        return self.source_mysql_host

    @property
    def SOURCE_MYSQL_PORT(self) -> int:
        return self.source_mysql_port

    @property
    def SOURCE_MYSQL_DB(self) -> str:
        return self.source_mysql_db

    @property
    def SOURCE_MYSQL_USER(self) -> str:
        return self.source_mysql_user

    @property
    def SOURCE_MYSQL_PASSWORD(self) -> str:
        return self.source_mysql_password

    @property
    def LLM_BASE_URL(self) -> str:
        return self.llm_base_url

    @property
    def LLM_API_KEY(self) -> str:
        return self.llm_api_key

    @property
    def LLM_MODEL(self) -> str:
        return self.llm_model

    @property
    def LLM_GUARDRAIL_ENABLED(self) -> bool:
        return self.llm_guardrail_enabled

    @property
    def LLM_GUARDRAIL_MODE(self) -> str:
        return self.llm_guardrail_mode

    @property
    def LLM_GUARDRAIL_SAMPLE_RATE(self) -> float:
        return self.llm_guardrail_sample_rate

    @property
    def LLM_GUARDRAIL_MIN_CONFIDENCE(self) -> float:
        return self.llm_guardrail_min_confidence

    @property
    def LLM_GUARDRAIL_A_QUERYKEY_WHITELIST(self) -> list[str]:
        return self.llm_guardrail_a_querykey_whitelist

    @property
    def LLM_GUARDRAIL_AUDIT_ENABLED(self) -> bool:
        return self.llm_guardrail_audit_enabled


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
