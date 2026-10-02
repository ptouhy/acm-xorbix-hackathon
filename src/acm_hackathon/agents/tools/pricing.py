"""Pricing and package optimization — official chiro_hackathon.visits schema."""

from __future__ import annotations

import pandas as pd

from acm_hackathon.agents.tools.base import ToolDefinition


def analyze_visit_revenue(visit_summary: pd.DataFrame) -> dict:
    """Identify high-volume services and revenue mix opportunities."""
    df = visit_summary.copy()
    by_service = (
        df.groupby("service_type")
        .agg(visit_count=("visit_count", "sum"), total_revenue=("total_revenue", "sum"))
        .reset_index()
    )
    by_service["avg_revenue"] = by_service["total_revenue"] / by_service["visit_count"]
    by_service = by_service.sort_values("total_revenue", ascending=False)

    package_share = (
        df.groupby("payment_type")["visit_count"].sum() / df["visit_count"].sum()
    ).to_dict()

    recommendations = []
    top = by_service.iloc[0]
    recommendations.append(
        f"Top revenue driver: {top['service_type']} (${top['total_revenue']:,.0f} total)."
    )
    pkg_pct = package_share.get("Package Plan", 0)
    if pkg_pct < 0.25:
        recommendations.append(
            f"Only {pkg_pct:.1%} of visits use Package Plan — upsell memberships at visit 3+."
        )
    else:
        recommendations.append(
            f"Package Plan is {pkg_pct:.1%} of visits — test premium tier for high-LTV patients."
        )

    return {
        "focus_area": "pricing",
        "by_service": by_service.to_dict(orient="records"),
        "payment_type_mix": package_share,
        "recommendations": recommendations,
    }


def analyze_marketing_roi(marketing_campaigns: pd.DataFrame) -> dict:
    """Find best/worst campaign channels by cost per conversion."""
    df = marketing_campaigns.copy()
    df["cost_per_lead"] = df["budget"] / df["leads_generated"].clip(lower=1)
    df["cost_per_conversion"] = df["budget"] / df["conversions"].clip(lower=1)
    df["conversion_rate"] = df["conversions"] / df["leads_generated"].clip(lower=1)

    by_channel = (
        df.groupby("channel")
        .agg(
            campaigns=("campaign_id", "count"),
            total_budget=("budget", "sum"),
            total_conversions=("conversions", "sum"),
            avg_cost_per_conversion=("cost_per_conversion", "mean"),
        )
        .reset_index()
        .sort_values("avg_cost_per_conversion")
    )

    best = by_channel.iloc[0] if len(by_channel) else None
    recommendations = []
    if best is not None:
        recommendations.append(
            f"Shift budget toward {best['channel']} (avg ${best['avg_cost_per_conversion']:.0f}/conversion)."
        )
    recommendations.append("Pause campaigns with cost/conversion 2× above channel median.")

    return {
        "focus_area": "pricing",
        "by_channel": by_channel.to_dict(orient="records"),
        "recommendations": recommendations,
    }


def get_pricing_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="analyze_visit_revenue",
            description="Analyze revenue by service type and payment mix.",
            focus_area="pricing",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda **_: analyze_visit_revenue(_data("visit_summary")),
        ),
        ToolDefinition(
            name="analyze_marketing_roi",
            description="Compare marketing channel cost per conversion.",
            focus_area="pricing",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda **_: analyze_marketing_roi(_data("marketing_campaigns")),
        ),
    ]


_DATA: dict[str, pd.DataFrame] = {}


def bind_data(tables: dict[str, pd.DataFrame]) -> None:
    global _DATA
    _DATA = tables


def _data(key: str) -> pd.DataFrame:
    if key not in _DATA:
        raise RuntimeError(f"Pricing tools require '{key}' — bind_data() first.")
    return _DATA[key]
