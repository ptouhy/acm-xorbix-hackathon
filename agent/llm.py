"""
LLM client — thin wrapper over a Databricks Foundation Model serving endpoint.

STEP EXPLANATION:
  Databricks serves chat models behind an OpenAI-compatible API, so tool calling
  uses the standard `tools=[...]` format. We normalize the reply into a plain dict
  so the agent loop (and tests) don't depend on any SDK types.

  Dependencies are imported lazily — nothing here needs installing until you call it.
  Inside a Databricks notebook/App: `databricks-sdk` (already available) is enough.
"""

from __future__ import annotations

import json
from typing import Any, Protocol


class LLMClient(Protocol):
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """Return {"content": str | None, "tool_calls": [{"id", "name", "arguments"}]}."""
        ...


class DatabricksLLM:
    def __init__(self, endpoint: str, temperature: float = 0.1, client: Any | None = None) -> None:
        self.endpoint = endpoint
        self.temperature = temperature
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            from databricks.sdk import WorkspaceClient  # lazy: only needed at call time

            self._client = WorkspaceClient().serving_endpoints.get_open_ai_client()
        return self._client

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        kwargs: dict[str, Any] = {
            "model": self.endpoint,
            "messages": messages,
            "temperature": self.temperature,
        }
        if tools:
            kwargs["tools"] = tools
        msg = self._get_client().chat.completions.create(**kwargs).choices[0].message

        calls = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append({"id": tc.id, "name": tc.function.name, "arguments": args})
        return {"content": msg.content, "tool_calls": calls}
