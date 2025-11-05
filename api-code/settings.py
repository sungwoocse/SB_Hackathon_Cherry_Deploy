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
    mongodb_uri: str = Field(
        default="mongodb://127.0.0.1:27017",
        alias="MONGODB_URI",
        description="MongoDB connection string",
    )
    mongodb_db_name: str = Field(
        default="cherry_deploy",
        alias="MONGODB_DB_NAME",
        description="MongoDB database name",
    )
    chatbot_repo_path: str = Field(
        default="/home/ec2-user/projects/SB_Hackathon_Cherry_Chatbot",
        alias="CHATBOT_REPO_PATH",
        description="Path to the frontend repository checked out on EC2.",
    )
    nginx_green_path: str = Field(
        default="/var/www/cherry-deploy/green",
        alias="NGINX_GREEN_PATH",
        description="Filesystem path for the Green deployment directory.",
    )
    nginx_blue_path: str = Field(
        default="/var/www/cherry-deploy/blue",
        alias="NGINX_BLUE_PATH",
        description="Filesystem path for the Blue deployment directory.",
    )
    nginx_live_symlink: str = Field(
        default="/var/www/cherry-deploy/current",
        alias="NGINX_LIVE_SYMLINK",
        description="Symlink that Nginx uses as its document root.",
    )
    deploy_dry_run: bool = Field(
        default=False,
        alias="DEPLOY_DRY_RUN",
        description="When true, deployment commands are logged but not executed.",
    )
    deploy_default_branch: str = Field(
        default="deploy",
        alias="DEPLOY_DEFAULT_BRANCH",
        description="Primary branch in Repo1 to pull for deployments.",
    )
    deploy_allowed_branches: str = Field(
        default="deploy,main",
        alias="DEPLOY_ALLOWED_BRANCHES",
        description="Comma-separated list of branches permitted for deploy operations.",
    )

    model_config = {"populate_by_name": True}

    @classmethod
    def from_env(cls) -> "Settings":
        return cls.model_validate(os.environ)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance built from environment variables."""
    return Settings.from_env()
