from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class LabSettings(BaseSettings):
    service_name: str = "inventory-service"
    role: Literal["order", "inventory"] = "inventory"
    inventory_url: str = "http://inventory-service:8000"
    downstream_timeout_seconds: float = 2.0

    model_config = SettingsConfigDict(
        env_prefix="AXIOMOPS_LAB_",
        extra="ignore",
    )
