from __future__ import annotations

import logging
import os
from pathlib import Path


logger = logging.getLogger("cherry-deploy.env")


def load_local_env(env_path: Path | str = Path(".env")) -> None:
    """Load key=value pairs from a local .env file without extra dependencies."""
    path = Path(env_path)
    if not path.exists():
        return

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            logger.warning("Skipping malformed .env line: %s", raw_line)
            continue

        key, value = line.split("=", 1)
        clean_key = key.strip()
        clean_value = value.strip().strip('"').strip("'")
        os.environ[clean_key] = clean_value
