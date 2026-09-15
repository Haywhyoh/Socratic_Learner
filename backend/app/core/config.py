from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://macpro@localhost:5432/socratic"
    test_database_url: str = "postgresql+psycopg://macpro@localhost:5432/socratic_test"
    secret_key: str = "dev-secret-key-not-for-production"
    access_token_expire_minutes: int = 60 * 24 * 7
    api_base_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:3000"
    algorithm: str = "HS256"
    llm_model: str = "stub"
    llm_api_key: str = ""
    anthropic_api_key: str = ""

    sandbox_enabled: bool = True
    sandbox_workspaces_root: str = str(_BACKEND_ROOT / "data" / "workspaces")
    sandbox_image: str = "socratic-sandbox-python:latest"
    sandbox_memory_mb: int = 512
    sandbox_cpus: float = 1.0
    sandbox_timeout_sec: int = 30
    sandbox_pids_limit: int = 64

    def resolved_llm_api_key(self) -> str:
        """Prefer provider-specific keys, then the generic LLM_API_KEY."""
        model = self.llm_model.lower()
        if model.startswith("anthropic:") or "claude" in model:
            return self.anthropic_api_key or self.llm_api_key
        return self.llm_api_key or self.anthropic_api_key


settings = Settings()
