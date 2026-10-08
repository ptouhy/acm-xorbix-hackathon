"""Load config/settings.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "settings.yaml"


def load_settings() -> dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)
