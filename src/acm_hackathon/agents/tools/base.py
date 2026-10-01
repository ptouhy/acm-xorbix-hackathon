"""Shared types for agent tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    focus_area: str
    parameters: dict[str, Any]
    handler: Callable[..., dict[str, Any]]

    def run(self, **kwargs: Any) -> dict[str, Any]:
        return self.handler(**kwargs)

    def as_openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
