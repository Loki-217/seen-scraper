# services/api/app/settings.py
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # 品牌名称
    api_title: str = "SeenFetch API"
    api_version: str = "1.0.0"
    app_name: str = "SeenFetch"
    app_tagline: str = "See it, Fetch it - Visual Web Data Extraction"
    app_description: str = "No-code web scraping tool for everyone"
    
    
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["*"])
    uvicorn_host: str = "127.0.0.1"
    uvicorn_port: int = 8000
    
    model_config = SettingsConfigDict(
        env_prefix="SEENFETCH_",  
        env_file=".env",
        case_sensitive=False,
    )

settings = Settings()