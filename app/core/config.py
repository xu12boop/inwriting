from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite:///./inwriting.db"
    secret_key: str = "dev-secret"
    zhipuai_api_key: str = ""  # 这里默认是空，如果 .env 没读到，就会报空
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # 规划 Agent 开关：开启后每轮面试前由规划 Agent 决定策略并调用工具检索；
    # 关闭则回退到原本的"角色 Prompt 直接生成"流程，零额外延迟。
    enable_planner: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()