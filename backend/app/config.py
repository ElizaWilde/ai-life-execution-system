from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    ollama_base_url: str = "https://ollama.com"
    ollama_model: str = "qwen3.5"
    ollama_api_key: str | None = None
    ollama_timeout_seconds: float = 120
    notion_api_key: str | None = None
    notion_database_id: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    smtp_timeout_seconds: float = 15
    telegram_bot_token: str | None = None
    telegram_timeout_seconds: float = 15
    scheduler_poll_seconds: float = 60
    scheduler_notification_grace_minutes: int = 60
    scheduler_stale_sending_minutes: int = 10
    jwt_secret: str = "dev-secret"

    class Config:
        env_file = ".env"


settings = Settings()
