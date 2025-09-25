# services/api/app/settings.py
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    api_title: str = "SeenScraper API"
    api_version: str = "0.1.0"
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["*"])
    uvicorn_host: str = "127.0.0.1"
    uvicorn_port: int = 8000

    # pydantic v2 风格配置
    model_config = SettingsConfigDict(
        env_prefix="SEEN_",
        env_file=".env",
        case_sensitive=False,
    )

settings = Settings()
