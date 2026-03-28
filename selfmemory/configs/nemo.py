import os
from typing import Any

from pydantic import BaseModel, Field


class NemoMemoryConfig(BaseModel):
    provider: str = Field(
        description="NeMo memory provider type: 'mem0', 'redis', or 'zep'"
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific configuration (host, port, api_key, etc.)",
    )

    @property
    def api_key(self) -> str | None:
        return self.config.get("api_key") or os.getenv("NEMO_MEMORY_API_KEY")

    @property
    def host(self) -> str | None:
        return self.config.get("host") or os.getenv("NEMO_MEMORY_HOST")
