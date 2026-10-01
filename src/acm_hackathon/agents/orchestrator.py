"""Agent orchestrator — tool selection and response synthesis."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from acm_hackathon.agents.tools import build_tool_registry
from acm_hackathon.agents.tools.base import ToolDefinition
from acm_hackathon.data.sample_data import all_sample_tables
from acm_hackathon.settings import AgentSettings


@dataclass
class AgentResponse:
    question: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    answer: str = ""
    mode: str = "heuristic"  # heuristic | databricks_model


# Keyword routing for local/demo runs without a live LLM endpoint
_TOOL_HINTS: dict[str, list[str]] = {
    "analyze_lead_pipeline": ["lead", "funnel", "convert", "pipeline", "source"],
    "score_lead_quality": ["score", "rank", "quality", "prospect"],
    "identify_at_risk_patients": ["retention", "churn", "drop", "inactive", "at risk", "risk"],
    "care_plan_completion_summary": ["care plan", "completion", "adherence"],
    "analyze_service_margins": ["margin", "pricing", "price", "profit", "revenue"],
    "recommend_membership_offers": ["membership", "package", "bundle", "plan"],
}


class ClinicGrowthAgent:
    """Agentic assistant for clinic growth focus areas."""

    def __init__(
        self,
        settings: AgentSettings | None = None,
        tools: dict[str, ToolDefinition] | None = None,
        tables: dict | None = None,
    ) -> None:
        self.settings = settings or AgentSettings.load()
        self.tables = tables or all_sample_tables()
        self.tools = tools or build_tool_registry(self.tables, self.settings)

    def _select_tools(self, question: str) -> list[str]:
        q = question.lower()
        selected: list[tuple[int, str]] = []
        for tool_name, hints in _TOOL_HINTS.items():
            if tool_name not in self.tools:
                continue
            score = sum(1 for h in hints if h in q)
            if score:
                selected.append((score, tool_name))
        selected.sort(reverse=True)
        if selected:
            return [name for _, name in selected[:2]]
        # Default: one tool per enabled focus area
        defaults = []
        for name, tool in self.tools.items():
            if tool.focus_area in self.settings.enabled_focus_areas:
                defaults.append(name)
        return defaults[:2]

    def _run_tools(self, tool_names: list[str]) -> list[dict[str, Any]]:
        results = []
        for name in tool_names:
            tool = self.tools[name]
            output = tool.run()
            results.append({"tool": name, "focus_area": tool.focus_area, "result": output})
        return results

    def _synthesize_heuristic(self, question: str, tool_results: list[dict[str, Any]]) -> str:
        lines = [f"Question: {question}", "", "Recommended actions:"]
        for tr in tool_results:
            recs = tr["result"].get("recommendations", [])
            lines.append(f"\n**{tr['focus_area'].title()}** (via `{tr['tool']}`)")
            if recs:
                for r in recs:
                    lines.append(f"- {r}")
            else:
                lines.append(f"- {json.dumps(tr['result'], default=str)[:300]}...")
        return "\n".join(lines)

    def _call_databricks_model(self, question: str, tool_results: list[dict[str, Any]]) -> str:
        """Invoke Foundation Model on Databricks when running in workspace."""
        try:
            from databricks.sdk import WorkspaceClient  # type: ignore[import-untyped]
            from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
        except ImportError as exc:
            raise RuntimeError("databricks-sdk required for model mode") from exc

        client = WorkspaceClient()
        tool_context = json.dumps(tool_results, default=str)
        messages = [
            ChatMessage(role=ChatMessageRole.SYSTEM, content=self.settings.system_prompt),
            ChatMessage(
                role=ChatMessageRole.USER,
                content=f"{question}\n\nTool results:\n{tool_context}",
            ),
        ]
        response = client.serving_endpoints.query(
            name=self.settings.model_endpoint,
            messages=[m.as_dict() for m in messages],  # type: ignore[arg-type]
            temperature=self.settings.temperature,
            max_tokens=self.settings.max_tokens,
        )
        choices = getattr(response, "choices", None) or []
        if choices:
            return choices[0].message.content or ""
        return self._synthesize_heuristic(question, tool_results)

    def ask(self, question: str, use_model: bool = False) -> AgentResponse:
        tool_names = self._select_tools(question)
        tool_results = self._run_tools(tool_names)

        if use_model:
            try:
                answer = self._call_databricks_model(question, tool_results)
                mode = "databricks_model"
            except Exception:
                answer = self._synthesize_heuristic(question, tool_results)
                mode = "heuristic_fallback"
        else:
            answer = self._synthesize_heuristic(question, tool_results)
            mode = "heuristic"

        return AgentResponse(
            question=question,
            tool_calls=tool_results,
            answer=answer,
            mode=mode,
        )


def parse_tool_calls_from_llm(text: str) -> list[dict[str, Any]]:
    """Extract JSON tool-call blocks from model output (for future multi-turn agents)."""
    pattern = re.compile(r"\{[^{}]*\"tool\"[^{}]*\}")
    return [json.loads(m.group()) for m in pattern.finditer(text)]
