"""Lead generation and conversion tools — official chiro_hackathon.leads schema."""

from __future__ import annotations

from datetime import date

import pandas as pd

from acm_hackathon.agents.tools.base import ToolDefinition

OPEN_STATUSES = {"New", "Contacted", "Qualified"}
SOURCE_WEIGHTS = {
    "Referral": 4,
    "Walk-In": 3,
    "Website Form": 2,
    "Phone Inquiry": 2,
    "Community Event": 2,
    "Social Media Ad": 1,
    "Insurance Directory": 1,
}


def _days_since(series: pd.Series, today: date) -> pd.Series:
    return (today - pd.to_datetime(series).dt.date).apply(lambda d: d.days)


def analyze_lead_pipeline(leads: pd.DataFrame, today: date | None = None) -> dict:
    """Summarize lead funnel, sources, and stale opportunities."""
    today = today or date.today()
    df = leads.copy()
    df["days_open"] = _days_since(df["created_date"], today)

    by_status = df.groupby("status").size().to_dict()
    stale = df[(df["status"].isin(OPEN_STATUSES)) & (df["days_open"] >= 3)]
    slow_response = df[(df["status"].isin(OPEN_STATUSES)) & (df["first_response_hours"] > 24)]

    by_source = (
        df.groupby("source")
        .agg(
            leads=("lead_id", "count"),
            conversions=("converted_flag", "sum"),
            avg_response_hours=("first_response_hours", "mean"),
        )
        .reset_index()
        .to_dict(orient="records")
    )

    conversion_rate = float(df["converted_flag"].mean()) if len(df) else 0.0
    recommendations = []
    if len(stale):
        recommendations.append(
            f"Follow up with {len(stale):,} stale leads open 3+ days (New/Contacted/Qualified)."
        )
    if len(slow_response):
        recommendations.append(
            f"Improve speed-to-lead: {len(slow_response):,} open leads waited 24+ hours for first response."
        )
    if conversion_rate < 0.25:
        recommendations.append(
            f"Conversion rate is {conversion_rate:.1%} — test referral incentives and same-day booking."
        )

    return {
        "focus_area": "leads",
        "summary": {
            "total_leads": len(df),
            "by_status": by_status,
            "conversion_rate": round(conversion_rate, 4),
        },
        "by_source": by_source,
        "stale_lead_count": len(stale),
        "slow_response_count": len(slow_response),
        "recommendations": recommendations,
    }


def score_lead_quality(leads: pd.DataFrame) -> dict:
    """Rank open leads by estimated conversion likelihood."""
    df = leads[leads["status"].isin(OPEN_STATUSES)].copy()
    df["score"] = df["source"].map(SOURCE_WEIGHTS).fillna(1)
    df.loc[df["first_response_hours"] <= 4, "score"] += 2
    df.loc[df["num_touchpoints"] >= 3, "score"] += 1
    df = df.sort_values("score", ascending=False)

    top = df.head(10)[["lead_id", "source", "status", "first_response_hours", "score"]]
    return {
        "focus_area": "leads",
        "ranked_leads": top.to_dict(orient="records"),
        "top_action": "Contact top-scored leads within 24 hours; prioritize Referral and Walk-In sources.",
    }


def get_lead_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="analyze_lead_pipeline",
            description="Analyze lead funnel, sources, response time, and stale opportunities.",
            focus_area="leads",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda **_: analyze_lead_pipeline(_data("leads")),
        ),
        ToolDefinition(
            name="score_lead_quality",
            description="Rank open leads by estimated conversion likelihood.",
            focus_area="leads",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda **_: score_lead_quality(_data("leads")),
        ),
    ]


_DATA: dict[str, pd.DataFrame] = {}


def bind_data(tables: dict[str, pd.DataFrame]) -> None:
    global _DATA
    _DATA = tables


def _data(key: str) -> pd.DataFrame:
    if key not in _DATA:
        raise RuntimeError(f"Lead tools require '{key}' — bind_data() first.")
    return _DATA[key]
