"""全局配置：全部通过环境变量 / .env 覆盖，默认值与历史行为保持一致。"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ---------- 应用信息 ----------
    app_name: str = "智聘引擎 InWriting API"
    app_version: str = "1.0.0"

    # ---------- 数据与存储 ----------
    # 生产环境建议写成绝对路径，例如 sqlite:////opt/inwriting/data/inwriting.db
    database_url: str = "sqlite:///./inwriting.db"
    # RAG 向量库持久化目录（chromadb PersistentClient）
    chroma_dir: str = "./.chroma"

    # ---------- 安全 ----------
    # 部署时务必替换；仍为默认值时启动会打印告警
    secret_key: str = "dev-secret"
    # 逗号分隔的允许来源；同域部署（Nginx 反代）可留空
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---------- 大模型（智谱 GLM）----------
    zhipuai_api_key: str = ""
    llm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    llm_model: str = "glm-4-flash"
    embedding_model: str = "embedding-3"
    llm_timeout_connect: float = 5.0
    llm_timeout_read: float = 20.0

    # ---------- 业务开关与限制 ----------
    # 规划 Agent 开关：开启后每轮由规划 Agent 决策并调用工具；关闭则回退原始 Prompt 流程
    enable_planner: bool = True
    # 简历上传大小上限（MB），防止大文件耗尽内存
    max_upload_mb: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def cors_origin_list(self) -> list[str]:
        """把 CORS_ORIGINS 拆成列表。"""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_default_secret(self) -> bool:
        """是否仍在使用示例密钥（部署时应为 False）。"""
        return self.secret_key in ("", "dev-secret", "dev-secret-key-change-me")


settings = Settings()
