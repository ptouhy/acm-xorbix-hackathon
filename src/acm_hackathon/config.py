"""Backward-compatible env config (prefer settings.py for YAML config)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class DatabricksConfig:
    host: str
    token: str | None
    catalog: str
    schema: str

    @classmethod
    def from_env(cls) -> DatabricksConfig:
        return cls(
            host=os.getenv("DATABRICKS_HOST", ""),
            token=os.getenv("DATABRICKS_TOKEN"),
            catalog=os.getenv("DATABRICKS_CATALOG", "main"),
            schema=os.getenv("DATABRICKS_SCHEMA", "clinic_hackathon"),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.host and self.token)
