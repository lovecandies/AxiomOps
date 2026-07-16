from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ControlPlaneSettings(BaseSettings):
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 13306
    mysql_database: str = "axiomops"
    mysql_user: str = "axiomops"
    mysql_password: str = "axiomops"
    rocketmq_endpoints: str = "127.0.0.1:18081"
    rocketmq_topic: str = "axiomops-incidents"
    rocketmq_consumer_group: str = "axiomops-investigation-dispatcher"
    relay_poll_seconds: float = 0.5
    relay_lease_seconds: int = 30
    prometheus_url: str = "http://127.0.0.1:19090"
    order_service_url: str = "http://127.0.0.1:18001"
    inventory_service_url: str = "http://127.0.0.1:18002"
    evidence_root: Path = Path("artifacts/evidence")
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-pro"
    deepseek_timeout_seconds: float = 60.0
    rca_max_model_calls: int = 8
    redis_url: str = "redis://127.0.0.1:16379"
    qdrant_url: str = "http://127.0.0.1:16333"
    qdrant_collection: str = "verified_rca_memory"
    memory_embedding_model: str = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    memory_embedding_dimension: int = 384
    memory_top_k: int = 3
    context_total_chars: int = 12000
    context_evidence_chars: int = 4000

    model_config = SettingsConfigDict(
        env_prefix="AXIOMOPS_CONTROL_",
        extra="ignore",
    )
