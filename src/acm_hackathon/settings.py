"""Load YAML configuration from the config/ directory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _load_yaml(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing config file: {path}")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@dataclass(frozen=True)
class AgentSettings:
    name: str
    description: str
    model_endpoint: str
    temperature: float
    max_tokens: int
    system_prompt: str
    enabled_focus_areas: tuple[str, ...]
    max_tool_rounds: int

    @classmethod
    def load(cls) -> AgentSettings:
        raw = _load_yaml("agent.yaml")["agent"]
        return cls(
            name=raw["name"],
            description=raw["description"].strip(),
            model_endpoint=raw["model"]["endpoint"],
            temperature=float(raw["model"]["temperature"]),
            max_tokens=int(raw["model"]["max_tokens"]),
            system_prompt=raw["system_prompt"].strip(),
            enabled_focus_areas=tuple(raw["enabled_focus_areas"]),
            max_tool_rounds=int(raw["max_tool_rounds"]),
        )


@dataclass(frozen=True)
class ClinicSettings:
    name: str
    location: str
    timezone: str
    services: tuple[dict[str, Any], ...]
    memberships: tuple[dict[str, Any], ...]

    @classmethod
    def load(cls) -> ClinicSettings:
        raw = _load_yaml("clinic.yaml")["clinic"]
        full = _load_yaml("clinic.yaml")
        return cls(
            name=raw["name"],
            location=raw["location"],
            timezone=raw["timezone"],
            services=tuple(full.get("services", [])),
            memberships=tuple(full.get("memberships", [])),
        )


@dataclass(frozen=True)
class DatabricksSettings:
    catalog: str
    schema: str
    tables: dict[str, str]
    volumes: dict[str, str]

    @classmethod
    def load(cls) -> DatabricksSettings:
        raw = _load_yaml("databricks.yaml")
        return cls(
            catalog=raw["catalog"],
            schema=raw["schema"],
            tables=dict(raw.get("tables", {})),
            volumes=dict(raw.get("volumes", {})),
        )

    def table_fqn(self, key: str) -> str:
        table = self.tables[key]
        return f"{self.catalog}.{self.schema}.{table}"
