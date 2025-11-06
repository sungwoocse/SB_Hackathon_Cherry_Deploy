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
    frontend_project_subdir: str = Field(
        default="frontend/my-dashboard",
        alias="FRONTEND_PROJECT_SUBDIR",
        description="Relative path to the frontend project within the chatbot repository.",
    )
    frontend_install_command: str = Field(
        default="npm install",
        alias="FRONTEND_INSTALL_COMMAND",
        description="Command used to install frontend dependencies.",
    )
    frontend_build_command: str = Field(
        default='bash -lc "pm2 delete frontend-dev 2>/dev/null || true; pm2 start npm --name frontend-dev -- run dev -- --hostname 0.0.0.0 --port 3000"',
        alias="FRONTEND_BUILD_COMMAND",
        description="Command used to build the frontend application.",
    )
    frontend_export_command: Optional[str] = Field(
        default=None,
        alias="FRONTEND_EXPORT_COMMAND",
        description=(
            "Optional command to generate static export artifacts after build. "
            "Set to blank to skip."
        ),
    )
    frontend_build_output_subdir: str = Field(
        default="",
        alias="FRONTEND_BUILD_OUTPUT_SUBDIR",
        description=(
            "Relative path to the directory containing deployable frontend assets "
            "after build/export."
        ),
    )
    preview_llm_model: str = Field(
        default="gemini-2.5-flash",
        alias="PREVIEW_LLM_MODEL",
        description="Generative model used to summarize upcoming deploy diffs.",
    )
    preview_diff_command: str = Field(
        default="git diff --name-status {base_commit}..HEAD",
        alias="PREVIEW_DIFF_COMMAND",
        description="Command template to summarize upcoming changes for LLM preview.",
    )
    preview_diff_max_chars: int = Field(
        default=4000,
        alias="PREVIEW_DIFF_MAX_CHARS",
        description="Maximum number of diff characters supplied to the preview LLM.",
    )

    model_config = {"populate_by_name": True}

    @classmethod
    def from_env(cls) -> "Settings":
        return cls.model_validate(os.environ)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance built from environment variables."""
    return Settings.from_env()
