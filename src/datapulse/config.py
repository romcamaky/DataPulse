"""
DataPulse configuration — loads environment variables from .env file.
All configuration lives here so other modules import from one place.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from dotenv import load_dotenv
import os


def get_anthropic_api_key() -> str:
    """
    Return the Anthropic API key for Claude calls (extractor, recommender).

    Not validated at import time so modules like the RSS collector can run without
    ``ANTHROPIC_API_KEY`` in ``.env``.
    """
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "Missing ANTHROPIC_API_KEY in .env. Required for datapulse.extractor "
            "and datapulse.recommender. Copy .env.example and add your Anthropic API key."
        )
    return key


def _find_project_root() -> Path:
    """
    Locate the project root directory by walking up from this file's location.

    The project root is assumed to be the directory containing the pyproject.toml
    file. This keeps configuration resolution consistent across environments.
    """
    # Start from the directory containing this file.
    current_dir: Path = Path(__file__).resolve().parent

    # Walk up the directory tree until we find pyproject.toml or reach the filesystem root.
    for parent in [current_dir, *current_dir.parents]:
        candidate: Path = parent / "pyproject.toml"
        if candidate.is_file():
            return parent

    # Fall back to the current directory if pyproject.toml cannot be found.
    # This is defensive: in normal development and CI, pyproject.toml should exist.
    return current_dir


# Resolve the absolute path to the project root.
_PROJECT_ROOT: Final[Path] = _find_project_root()

# Resolve the .env path at the project root.
_ENV_PATH: Final[Path] = _PROJECT_ROOT / ".env"

# Load environment variables from the .env file, if it exists.
# This keeps local development configuration outside of version control.
load_dotenv(dotenv_path=_ENV_PATH)

# Read Supabase configuration from environment variables.
SUPABASE_URL: Final[str] = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: Final[str] = os.getenv("SUPABASE_KEY", "")


def _validate_required_env_var(name: str, value: str) -> None:
    """
    Validate that a required environment variable is present and non-empty.

    Raises a clear, user-friendly error if the variable is missing so that
    developers immediately know to copy and fill in .env.example.
    """
    if not value:
        raise RuntimeError(
            f"Missing {name} in .env file. "
            "Copy .env.example and fill in your Supabase credentials."
        )


# Validate configuration eagerly at import time so failures surface early.
_validate_required_env_var("SUPABASE_URL", SUPABASE_URL)
_validate_required_env_var("SUPABASE_KEY", SUPABASE_KEY)

