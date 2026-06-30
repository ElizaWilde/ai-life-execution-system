from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_api_key: str | None = None
    notion_api_key: str | None = None
    notion_database_id: str | None = None
    jwt_secret: str = "dev-secret"

    class Config:
        env_file = ".env"


settings = Settings()
