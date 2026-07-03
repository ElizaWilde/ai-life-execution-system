from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    ollama_base_url: str = "https://ollama.com"
    ollama_model: str = "qwen3.5"
    ollama_api_key: str | None = None
    ollama_timeout_seconds: float = 120
    notion_api_key: str | None = None
    notion_database_id: str | None = None
    jwt_secret: str = "dev-secret"

    class Config:
        env_file = ".env"


settings = Settings()
