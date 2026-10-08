"""
Orchestrator — runs all tools and ranks actions by $ impact.

STEP EXPLANATION:
  This is the "agentic" part: it coordinates multiple tools, merges results,
  and produces one prioritized briefing (not just one SQL query).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent.settings import load_settings
from agent.tools import (
    find_churn_risk_patients,
    find_revenue_leaks,
    find_stale_leads,
    find_top_lead_sources,
)


@dataclass
class BriefingResult:
    question: str
    actions: list[dict] = field(default_factory=list)
    total_estimated_impact_usd: float = 0.0
    tool_outputs: list[dict] = field(default_factory=list)
    briefing_text: str = ""
    trace: list[dict] = field(default_factory=list)  # tool_call/tool_result steps (agentic mode)
    mode: str = "deterministic"  # "agentic" when the LLM drove the run


def rank_actions(tool_results: list[dict]) -> list[dict]:
    """Sort analysis results by estimated_impact_usd → top 5 actions.

    Diagnostic and action tools explain or act on those findings, so ranking them too
    would double-count the same dollars.
    """
    analysis = [r for r in tool_results if r.get("kind", "analysis") == "analysis"]
    ranked = sorted(analysis, key=lambda r: r.get("estimated_impact_usd", 0), reverse=True)
    actions = []
    for i, r in enumerate(ranked[:5], start=1):
        actions.append({
            "rank": i,
            "focus": r["focus"],
            "tool": r["tool"],
            "estimated_impact_usd": r["estimated_impact_usd"],
            "recommendation": r["recommendation"],
            "metrics": r.get("metrics", {}),
        })
    return actions


def format_briefing(question: str, actions: list[dict], total_impact: float) -> str:
    """Human-readable briefing for demo + MLflow log."""
    lines = [
        f"# Revenue Briefing Agent",
        f"**Question:** {question}",
        "",
        f"**Total estimated opportunity:** ${total_impact:,.0f}",
        "",
        "## Top prioritized actions",
        "",
    ]
    for a in actions:
        lines.append(
            f"{a['rank']}. **[{a['focus'].upper()}]** ${a['estimated_impact_usd']:,.0f} — {a['recommendation']}"
        )
    lines.append("")
    lines.append("*Estimates use configurable economics in config/settings.yaml*")
    return "\n".join(lines)


class RevenueBriefingAgent:
    """Runs tools on Spark data and returns a ranked daily briefing."""

    def __init__(self, spark: Any, catalog: str | None = None, schema: str | None = None) -> None:
        self.spark = spark
        self.settings = load_settings()
        self.catalog = catalog or self.settings["catalog"]
        self.schema = schema or self.settings["schema"]

    def run(self, question: str | None = None) -> BriefingResult:
        question = question or self.settings["agent"]["default_question"]
        s = self.settings

        tool_outputs = [
            find_stale_leads(self.spark, self.catalog, self.schema, s),
            find_churn_risk_patients(self.spark, self.catalog, self.schema, s),
            find_revenue_leaks(self.spark, self.catalog, self.schema, s),
            find_top_lead_sources(self.spark, self.catalog, self.schema, s),
        ]

        actions = rank_actions(tool_outputs)
        total = sum(a["estimated_impact_usd"] for a in actions)
        text = format_briefing(question, actions, total)

        return BriefingResult(
            question=question,
            actions=actions,
            total_estimated_impact_usd=total,
            tool_outputs=tool_outputs,
            briefing_text=text,
        )
