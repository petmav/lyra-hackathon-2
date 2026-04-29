from functools import lru_cache

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    data_mode: Literal["demo", "production"] = Field(default="demo", alias="PRAETOR_DATA_MODE")
    seed_demo_data: bool = Field(default=False, alias="PRAETOR_SEED_DEMO_DATA")
    auto_migrate: bool = Field(default=True, alias="PRAETOR_AUTO_MIGRATE")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    google_api_key: str | None = Field(default=None, alias="GOOGLE_API_KEY")
    default_model_provider: str = Field(default="openai", alias="DEFAULT_MODEL_PROVIDER")
    default_model_name: str = Field(default="gpt-5.4-mini", alias="DEFAULT_MODEL_NAME")
    agent_model_mode: Literal["auto", "live", "dry_run"] = Field(
        default="auto",
        alias="PRAETOR_AGENT_MODEL_MODE",
    )
    pg_dsn: str = Field(
        default="postgresql+asyncpg://praetor:praetor@localhost:5432/praetor",
        alias="PG_DSN",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    s3_endpoint: str = Field(default="http://localhost:9000", alias="S3_ENDPOINT")
    s3_access_key: str = Field(default="praetor", alias="S3_ACCESS_KEY")
    s3_secret_key: str = Field(default="praetor-secret", alias="S3_SECRET_KEY")
    opa_url: str = Field(default="http://localhost:8181", alias="OPA_URL")
    sandbox_image: str = Field(default="compose-sandbox:latest", alias="SANDBOX_IMAGE")
    sandbox_orchestrator_url: str | None = Field(
        default=None,
        alias="SANDBOX_ORCHESTRATOR_URL",
    )
    dev_bearer: str = Field(default="dev", alias="DEV_BEARER")
    web_origin: str = Field(default="http://localhost:3000", alias="WEB_ORIGIN")

    @property
    def data_backend(self) -> str:
        return "in_memory" if self.data_mode == "demo" else "postgres"


@lru_cache
def get_settings() -> Settings:
    return Settings()
