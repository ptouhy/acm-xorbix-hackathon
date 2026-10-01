"""Pricing, packages, and membership optimization tools."""

from __future__ import annotations

import pandas as pd

from acm_hackathon.agents.tools.base import ToolDefinition


def analyze_service_margins(service_pricing: pd.DataFrame) -> dict:
    """Identify high-volume / low-margin services for pricing adjustments."""
    df = service_pricing.copy()
    df["profit_per_visit"] = df["price"] * df["margin_pct"]
    df["monthly_profit"] = df["profit_per_visit"] * df["monthly_volume"]
    low_margin_high_vol = df[(df["margin_pct"] < 0.55) & (df["monthly_volume"] >= 40)]

    recommendations = []
    for row in low_margin_high_vol.itertuples():
        recommendations.append(
            f"Review {row.service_name}: ${row.price:.0f} at {row.margin_pct:.0%} margin, "
            f"{row.monthly_volume} visits/mo — consider +5–10% or bundle into membership."
        )
    if not recommendations:
        recommendations.append("Margins look healthy; test membership upsell on high-LTV patients.")

    return {
        "focus_area": "pricing",
        "services": df.sort_values("monthly_profit", ascending=False).to_dict(orient="records"),
        "recommendations": recommendations,
    }


def recommend_membership_offers(
    service_pricing: pd.DataFrame,
    memberships: list[dict],
) -> dict:
    """Compare à la carte vs membership value for common visit patterns."""
    adj = service_pricing[service_pricing["service_id"] == "adjustment"].iloc[0]
    per_visit = float(adj["price"])
    offers = []
    for m in memberships:
        per_visit_pkg = m["price"] / m["visits"]
        savings = per_visit - per_visit_pkg
        offers.append(
            {
                "membership_id": m["id"],
                "name": m["name"],
                "price": m["price"],
                "effective_per_visit": round(per_visit_pkg, 2),
                "savings_vs_single": round(savings, 2),
            }
        )
    return {
        "focus_area": "pricing",
        "membership_offers": offers,
        "recommendations": [
            "Pitch Wellness 4-Pack to patients on visit 3 of an informal series.",
            "Highlight Care Plan 12-Visit savings at initial eval.",
        ],
    }


def get_pricing_tools(memberships: list[dict] | None = None) -> list[ToolDefinition]:
    memberships = memberships or []

    return [
        ToolDefinition(
            name="analyze_service_margins",
            description="Find pricing opportunities by margin and volume.",
            focus_area="pricing",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda **_: analyze_service_margins(_service_pricing()),
        ),
        ToolDefinition(
            name="recommend_membership_offers",
            description="Compare membership packages vs single-visit pricing.",
            focus_area="pricing",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda **_: recommend_membership_offers(_service_pricing(), memberships),
        ),
    ]


_DATA: dict[str, pd.DataFrame] = {}


def bind_data(tables: dict[str, pd.DataFrame]) -> None:
    global _DATA
    _DATA = tables


def _service_pricing() -> pd.DataFrame:
    return _DATA["service_pricing"]
