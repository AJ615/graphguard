"""GraphGuard configuration — reads from environment / .env file."""
from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # FalkorDB
    falkordb_host: str = Field(default="localhost", alias="FALKORDB_HOST")
    falkordb_port: int = Field(default=6379, alias="FALKORDB_PORT")
    falkordb_password: str = Field(default="", alias="FALKORDB_PASSWORD")
    falkordb_graph: str = Field(default="graphguard", alias="FALKORDB_GRAPH")

    # LLM
    llm_provider: str = Field(default="demo", alias="LLM_PROVIDER")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_model: str = Field(
        default="claude-3-5-haiku-20241022", alias="LLM_MODEL"
    )

    # Backend
    backend_host: str = Field(default="0.0.0.0", alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")

    # Tenant
    default_tenant_id: str = Field(
        default="tenant_default", alias="DEFAULT_TENANT_ID"
    )

    # Demo mode
    demo_mode: bool = Field(default=True, alias="DEMO_MODE")

    @property
    def is_llm_enabled(self) -> bool:
        return bool(self.llm_api_key) and self.llm_provider != "demo"


settings = Settings()
