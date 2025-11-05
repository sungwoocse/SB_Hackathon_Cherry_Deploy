from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Runtime configuration resolved from environment variables."""

    gemini_api_key: Optional[str] = Field(
        default=None, alias="GEMINI_API_KEY", description="Google Gemini API key"
    )

    model_config = {"populate_by_name": True}

    @classmethod
    def from_env(cls) -> "Settings":
        return cls.model_validate(os.environ)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance built from environment variables."""
    return Settings.from_env()
