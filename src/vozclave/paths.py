"""Where VozClave keeps its config, models and voiceprint (never inside the repo)."""

import os
from pathlib import Path


def home() -> Path:
    """Per-user folder: %APPDATA%\\vozclave on Windows, ~/.config/vozclave elsewhere.

    Set VOZCLAVE_HOME to override it (useful for tests or portable installs).
    """
    override = os.environ.get("VOZCLAVE_HOME")
    if override:
        return Path(override)
    if os.name == "nt" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "vozclave"
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "vozclave"


def models_dir() -> Path:
    return home() / "models"


def voiceprint_path() -> Path:
    return home() / "voiceprint.npy"


def default_config_path() -> Path:
    """`./vozclave.toml` wins over the per-user config if it exists."""
    local = Path.cwd() / "vozclave.toml"
    return local if local.exists() else home() / "config.toml"
