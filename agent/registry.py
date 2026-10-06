"""
Tool registry — describes each tool to the LLM (JSON schema) and dispatches calls.

STEP EXPLANATION:
  The LLM never touches Spark. It sees a name + description for each tool,
  decides which to call, and we run the matching Python function.
"""

from __future__ import annotations

from typing import Any, Callable

from agent.tools import (
    find_churn_risk_patients,
    find_revenue_leaks,
    find_stale_leads,
    find_top_lead_sources,
)

_NO_ARGS = {"type": "object", "properties": {}, "additionalProperties": False}

# name -> (function, description shown to the LLM)
_SPARK_TOOLS: dict[str, tuple[Callable[..., dict], str]] = {
    "find_stale_leads": (
        find_stale_leads,
        "LEADS. Counts open leads (New/Contacted/Qualified) that have gone unworked past the "
        "stale threshold, plus slow-response stats. Use for questions about pipeline, follow-up, "
        "or new patient acquisition.",
    ),
    "find_top_lead_sources": (
        find_top_lead_sources,
        "LEADS. Ranks the best-converting lead sources among open leads so staff know whom to "
        "call first. Use for questions about which sources or channels to prioritize for outreach.",
    ),
    "find_churn_risk_patients": (
        find_churn_risk_patients,
        "RETENTION. Counts Active patients with a high churn-risk score and estimates the revenue "
        "recoverable by re-engaging them. Use for questions about retention, dropouts, or lapsed patients.",
    ),
    "find_revenue_leaks": (
        find_revenue_leaks,
        "PRICING. Finds revenue leaks: appointment no-show rate, share of visits on Package Plans, "
        "and the cheapest marketing channel per conversion. Use for questions about pricing, "
        "packages, no-shows, or marketing spend.",
    ),
}

RANK_TOOL = "rank_actions"


def tool_specs() -> list[dict]:
    """OpenAI-style function specs (Databricks Foundation Model endpoints accept this format)."""
    specs = [
        {
            "type": "function",
            "function": {"name": name, "description": desc, "parameters": _NO_ARGS},
        }
        for name, (_, desc) in _SPARK_TOOLS.items()
    ]
    specs.append({
        "type": "function",
        "function": {
            "name": RANK_TOOL,
            "description": (
                "Ranks every analysis result gathered so far by estimated dollar impact. "
                "Call this once, after you have run the analysis tools you need."
            ),
            "parameters": _NO_ARGS,
        },
    })
    return specs


def spark_tool_names() -> list[str]:
    return list(_SPARK_TOOLS)


def run_spark_tool(name: str, spark: Any, catalog: str, schema: str, settings: dict) -> dict:
    fn, _ = _SPARK_TOOLS[name]
    return fn(spark, catalog, schema, settings)
