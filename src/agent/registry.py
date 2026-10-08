"""
Tool registry — describes each tool to the LLM (JSON schema) and dispatches calls.

STEP EXPLANATION:
  The LLM never touches Spark. It sees a name + description for each tool,
  decides which to call (and with what arguments), and we run the matching Python function.

  Tool kinds:
    analysis    — measures an opportunity and estimates $ impact (ranked by rank_actions)
    diagnostic  — explains WHY something is happening (Reason)
    action      — produces a concrete next step, e.g. a contact list + message (Act)
"""

from __future__ import annotations

from typing import Any, Callable

from agent.tools import (
    diagnose_lead_response,
    diagnose_no_shows,
    draft_outreach,
    find_churn_risk_patients,
    find_revenue_leaks,
    find_stale_leads,
    find_top_lead_sources,
)

_NO_ARGS = {"type": "object", "properties": {}, "additionalProperties": False}

_OUTREACH_ARGS = {
    "type": "object",
    "properties": {
        "segment": {
            "type": "string",
            "enum": ["stale_leads", "churn_risk_patients"],
            "description": "Which group of people to contact.",
        },
        "limit": {
            "type": "integer",
            "description": "How many people to put on today's call list (1-25, default 10).",
        },
    },
    "required": ["segment"],
    "additionalProperties": False,
}

# name -> (function, description shown to the LLM, JSON-schema for arguments)
_SPARK_TOOLS: dict[str, tuple[Callable[..., dict], str, dict]] = {
    "find_stale_leads": (
        find_stale_leads,
        "ANALYSIS / LEADS. Counts open leads (New/Contacted/Qualified) that have gone unworked past "
        "the stale threshold, plus slow-response stats. Use for questions about pipeline, follow-up, "
        "or new patient acquisition.",
        _NO_ARGS,
    ),
    "find_top_lead_sources": (
        find_top_lead_sources,
        "ANALYSIS / LEADS. Ranks the best-converting lead sources among open leads so staff know "
        "whom to call first. Use for questions about which sources or channels to prioritize.",
        _NO_ARGS,
    ),
    "find_churn_risk_patients": (
        find_churn_risk_patients,
        "ANALYSIS / RETENTION. Counts Active patients who have stopped coming (last visit 60-180 days "
        "ago) and estimates the revenue recoverable by re-engaging them. Use for retention, dropout, "
        "or lapsing-patient questions.",
        _NO_ARGS,
    ),
    "find_revenue_leaks": (
        find_revenue_leaks,
        "ANALYSIS / PRICING. Prices the revenue lost to no-shows over the last 12 months, and reports "
        "package-plan economics and marketing cost per conversion by channel. Use for pricing, "
        "packages, no-shows, or marketing-spend questions.",
        _NO_ARGS,
    ),
    "diagnose_no_shows": (
        diagnose_no_shows,
        "DIAGNOSTIC (explains WHY). Breaks no-shows down by appointment type, booking channel, "
        "booking lead time and location, and returns the segments running above the clinic baseline. "
        "Use when asked why appointments are being missed or where to aim reminders.",
        _NO_ARGS,
    ),
    "diagnose_lead_response": (
        diagnose_lead_response,
        "DIAGNOSTIC (explains WHY). Tests whether speed of first response changes lead conversion. "
        "Use when asked why leads are not converting or whether response time matters.",
        _NO_ARGS,
    ),
    "draft_outreach": (
        draft_outreach,
        "ACTION. Builds today's prioritized contact list plus a message template for ONE segment, and "
        "stages it in the outreach_queue table as pending staff approval. "
        "Pick the segment the question is about: 'churn_risk_patients' for patients leaving / "
        "retention / lapsing; 'stale_leads' for leads / new-patient follow-up. Use when staff ask "
        "who to call, what to do next, or for outreach copy.",
        _OUTREACH_ARGS,
    ),
}

RANK_TOOL = "rank_actions"
PLAN_TOOL = "record_plan"


def tool_specs() -> list[dict]:
    """OpenAI-style function specs (Databricks Foundation Model endpoints accept this format)."""
    specs = [
        {
            "type": "function",
            "function": {"name": name, "description": desc, "parameters": params},
        }
        for name, (_, desc, params) in _SPARK_TOOLS.items()
    ]
    specs.append({
        "type": "function",
        "function": {
            "name": PLAN_TOOL,
            "description": (
                "Record your plan BEFORE calling any other tool: 2-5 short steps saying which "
                "tools you will use and why. Call this first, once."
            ),
            "parameters": {
                "type": "object",
                "properties": {"steps": {"type": "array", "items": {"type": "string"}}},
                "required": ["steps"],
            },
        },
    })
    specs.append({
        "type": "function",
        "function": {
            "name": RANK_TOOL,
            "description": (
                "Ranks the ANALYSIS tool results gathered so far by estimated dollar impact. "
                "Call this once, after you have run the analysis tools you need."
            ),
            "parameters": _NO_ARGS,
        },
    })
    return specs


def spark_tool_names() -> list[str]:
    return list(_SPARK_TOOLS)


def run_spark_tool(
    name: str, spark: Any, catalog: str, schema: str, settings: dict, args: dict | None = None
) -> dict:
    fn = _SPARK_TOOLS[name][0]
    return fn(spark, catalog, schema, settings, **(args or {}))
