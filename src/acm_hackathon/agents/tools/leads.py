"""Lead generation and conversion tools."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from acm_hackathon.agents.tools.base import ToolDefinition


def _days_since(series: pd.Series, today: date) -> pd.Series:
    return (today - pd.to_datetime(series).dt.date).apply(lambda d: d.days)


def analyze_lead_pipeline(leads: pd.DataFrame, today: date | None = None) -> dict:
    """Summarize lead funnel and flag stale opportunities."""
    today = today or date.today()
    df = leads.copy()
    df["days_open"] = _days_since(df["created_date"], today)

    by_status = df.groupby("status").size().to_dict()
    stale = df[(df["status"].isin(["new", "contacted"])) & (df["days_open"] >= 3)]
    by_source = (
        df.groupby("source")
        .agg(leads=("lead_id", "count"), pipeline_value=("estimated_value", "sum"))
        .reset_index()
        .to_dict(orient="records")
    )

    recommendations = []
    if len(stale):
        recommendations.append(
            f"Follow up with {len(stale)} stale leads (3+ days without conversion)."
        )
    if by_status.get("new", 0) >= 2:
        recommendations.append("Prioritize same-day outreach for new web/social leads.")

    return {
        "focus_area": "leads",
        "summary": {
            "total_leads": len(df),
            "by_status": by_status,
            "pipeline_value": float(df["estimated_value"].sum()),
        },
        "by_source": by_source,
        "stale_leads": stale[["lead_id", "name", "source", "status", "days_open"]].to_dict(
            orient="records"
        ),
        "recommendations": recommendations,
    }


def score_lead_quality(leads: pd.DataFrame) -> dict:
    """Rank open leads by conversion likelihood (heuristic demo scoring)."""
    df = leads[leads["status"].isin(["new", "contacted", "booked"])].copy()
    source_weight = {"referral": 3, "walk_in": 2, "google_ads": 1, "instagram": 1}
    df["score"] = df["source"].map(source_weight).fillna(0)
    df.loc[df["status"] == "booked", "score"] += 2
    df = df.sort_values("score", ascending=False)

    return {
        "focus_area": "leads",
        "ranked_leads": df[["lead_id", "name", "source", "status", "score"]].to_dict(
            orient="records"
        ),
        "top_action": "Call top-scored leads within 24 hours; offer initial eval promo.",
    }


def get_lead_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="analyze_lead_pipeline",
            description="Analyze lead funnel, sources, and stale opportunities.",
            focus_area="leads",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda **_: analyze_lead_pipeline(_context_leads()),
        ),
        ToolDefinition(
            name="score_lead_quality",
            description="Rank open leads by estimated conversion likelihood.",
            focus_area="leads",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda **_: score_lead_quality(_context_leads()),
        ),
    ]


# Module-level data context set by orchestrator before tool runs
_DATA: dict[str, pd.DataFrame] = {}


def bind_data(tables: dict[str, pd.DataFrame]) -> None:
    global _DATA
    _DATA = tables


def _context_leads() -> pd.DataFrame:
    if "leads" not in _DATA:
        raise RuntimeError("Lead tools require 'leads' table — bind_data() first.")
    return _DATA["leads"]
