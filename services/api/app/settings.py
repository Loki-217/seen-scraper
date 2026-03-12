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
    
    # 🔥 火山引擎 DeepSeek 配置
    deepseek_api_key: str = Field(
        default="",
        description="api key"
    )
    deepseek_endpoint_id: str = Field(
        default="",
        description="接入点 ID"
    )
    deepseek_api_base: str = Field(
        default="https://ark.cn-beijing.volces.com/api/v3",
        description="火山引擎 API Base URL"
    )
    ai_enabled: bool = Field(
        default=True,
        description="是否启用 AI 功能（如果 API Key 或 Endpoint ID 为空，自动禁用）"
    )

    model_config = SettingsConfigDict(
        env_prefix="SEENFETCH_",
        env_file=".env",
        case_sensitive=False,
    )

settings = Settings()