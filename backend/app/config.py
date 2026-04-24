from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://dealhunter:dealhunter@postgres:5432/dealhunter"
    redis_url: str = "redis://redis:6379/0"
    secret_key: str = "change-me-in-production"
    debug: bool = False
    api_title: str = "DealHunter API"
    api_version: str = "1.0.0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
