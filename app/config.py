from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    openai_api_key: str = ""
    deepseek_api_key: str = ""
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    langsmith_tracing: bool = True
    langsmith_api_key: str = ""
    langsmith_project: str = "epistemy-sessions"
    database_url: str = "sqlite:///./epistemy.db"
    checkpoint_db_path: str = "./checkpoints.db"
    secret_key: str = "dev-secret"
    use_fallback_transcripts: bool = True


settings = Settings()
