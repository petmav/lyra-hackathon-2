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
    anthropic_api_key_ref: str = Field(default="secret:anthropic_api_key", alias="ANTHROPIC_API_KEY_REF")
    openai_api_key_ref: str = Field(default="secret:openai_api_key", alias="OPENAI_API_KEY_REF")
    google_api_key_ref: str = Field(default="secret:google_api_key", alias="GOOGLE_API_KEY_REF")
    default_model_provider: str = Field(default="openai", alias="DEFAULT_MODEL_PROVIDER")
    default_model_name: str = Field(default="gpt-5.4-mini", alias="DEFAULT_MODEL_NAME")
    agent_model_mode: Literal["auto", "live", "dry_run"] = Field(
        default="auto",
        alias="PRAETOR_AGENT_MODEL_MODE",
    )
    workflow_execution_mode: Literal["sync", "queued"] = Field(
        default="sync",
        alias="PRAETOR_WORKFLOW_EXECUTION_MODE",
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
    auth_mode: Literal["dev_bearer", "jwt", "disabled"] = Field(default="dev_bearer", alias="PRAETOR_AUTH_MODE")
    dev_bearer: str = Field(default="dev", alias="DEV_BEARER")
    jwt_secret: str | None = Field(default=None, alias="PRAETOR_JWT_SECRET")
    jwt_issuer: str | None = Field(default=None, alias="PRAETOR_JWT_ISSUER")
    jwt_audience: str | None = Field(default=None, alias="PRAETOR_JWT_AUDIENCE")
    jwt_required_read_role: str = Field(default="viewer", alias="PRAETOR_JWT_REQUIRED_READ_ROLE")
    jwt_required_write_role: str = Field(default="operator", alias="PRAETOR_JWT_REQUIRED_WRITE_ROLE")
    secret_backend: Literal["env", "vault", "env_then_vault", "vault_then_env"] = Field(
        default="env",
        alias="PRAETOR_SECRET_BACKEND",
    )
    vault_addr: str | None = Field(default=None, alias="VAULT_ADDR")
    vault_token: str | None = Field(default=None, alias="VAULT_TOKEN")
    vault_namespace: str | None = Field(default=None, alias="VAULT_NAMESPACE")
    vault_kv_mount: str = Field(default="secret", alias="VAULT_KV_MOUNT")
    vault_path_prefix: str = Field(default="praetor", alias="PRAETOR_VAULT_PATH_PREFIX")
    vault_timeout_seconds: float = Field(default=2.0, alias="VAULT_TIMEOUT_SECONDS")
    web_origin: str = Field(default="http://localhost:3000", alias="WEB_ORIGIN")

    @property
    def data_backend(self) -> str:
        return "in_memory" if self.data_mode == "demo" else "postgres"


@lru_cache
def get_settings() -> Settings:
    return Settings()
