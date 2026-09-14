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
    algorithm: str = "HS256"
    llm_model: str = "stub"
    llm_api_key: str = ""


settings = Settings()
