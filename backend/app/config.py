from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    openai_api_key: str | None = None
    notion_api_key: str | None = None
    notion_database_id: str | None = None
    jwt_secret: str = "dev-secret"

    class Config:
        env_file = ".env"


settings = Settings()
