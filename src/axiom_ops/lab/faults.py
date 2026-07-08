import asyncio
from dataclasses import asdict, dataclass
from typing import Literal


FaultMode = Literal["none", "latency", "error_rate", "unavailable"]


@dataclass(frozen=True)
class FaultConfig:
    mode: FaultMode = "none"
    delay_ms: int = 0
    error_rate: float = 0.0


class FaultState:
    """Process-local deterministic fault state for the inventory service."""

    def __init__(self) -> None:
        self._config = FaultConfig()
        self._request_count = 0
        self._lock = asyncio.Lock()

    async def configure(self, config: FaultConfig) -> dict[str, int | float | str]:
        async with self._lock:
            self._config = config
            self._request_count = 0
            return asdict(self._config)

    async def reset(self) -> dict[str, int | float | str]:
        return await self.configure(FaultConfig())

    async def next_request(self) -> tuple[FaultConfig, bool]:
        async with self._lock:
            self._request_count += 1
            config = self._config
            threshold = round(config.error_rate * 100)
            deterministic_bucket = (self._request_count * 37) % 100
            should_fail = config.mode == "error_rate" and deterministic_bucket < threshold
            return config, should_fail

    async def snapshot(self) -> dict[str, int | float | str]:
        async with self._lock:
            return {**asdict(self._config), "request_count": self._request_count}
