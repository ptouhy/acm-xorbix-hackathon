"""Patient retention and care-plan completion tools."""

from __future__ import annotations

from datetime import date

import pandas as pd

from acm_hackathon.agents.tools.base import ToolDefinition


def identify_at_risk_patients(
    patients: pd.DataFrame,
    care_plans: pd.DataFrame,
    today: date | None = None,
    inactive_days: int = 45,
) -> dict:
    """Find patients at risk of dropping off or abandoning care plans."""
    today = today or date.today()
    p = patients.copy()
    p["last_visit_date"] = pd.to_datetime(p["last_visit_date"])
    p["days_since_visit"] = p["last_visit_date"].apply(
        lambda d: (today - d.date()).days if pd.notna(d) else 999
    )

    inactive = p[p["days_since_visit"] >= inactive_days]
    cp = care_plans[care_plans["status"] == "active"].copy()
    cp["completion_pct"] = cp["visits_completed"] / cp["visits_prescribed"]
    stalled = cp[cp["completion_pct"] < 0.5].merge(p, on="patient_id", how="left")

    recommendations = []
    if len(inactive):
        recommendations.append(
            f"Re-engagement campaign for {len(inactive)} patients inactive {inactive_days}+ days."
        )
    if len(stalled):
        recommendations.append(
            f"Care-plan check-ins for {len(stalled)} patients below 50% completion."
        )

    return {
        "focus_area": "retention",
        "inactive_patients": inactive[
            ["patient_id", "name", "days_since_visit", "lifetime_value"]
        ].to_dict(orient="records"),
        "stalled_care_plans": stalled[
            [
                "patient_id",
                "name",
                "visits_completed",
                "visits_prescribed",
                "completion_pct",
            ]
        ].to_dict(orient="records"),
        "recommendations": recommendations,
    }


def care_plan_completion_summary(care_plans: pd.DataFrame) -> dict:
    """Aggregate care plan completion metrics."""
    df = care_plans.copy()
    df["completion_pct"] = df["visits_completed"] / df["visits_prescribed"]
    by_status = df.groupby("status").agg(
        plans=("care_plan_id", "count"),
        avg_completion=("completion_pct", "mean"),
    )
    return {
        "focus_area": "retention",
        "by_status": by_status.reset_index().to_dict(orient="records"),
        "recommendations": [
            "Celebrate completed plans with referral ask.",
            "Offer payment-plan reminder for active plans under 60% completion.",
        ],
    }


def get_retention_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="identify_at_risk_patients",
            description="Find inactive patients and stalled care plans.",
            focus_area="retention",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda **_: identify_at_risk_patients(_patients(), _care_plans()),
        ),
        ToolDefinition(
            name="care_plan_completion_summary",
            description="Summarize care plan completion by status.",
            focus_area="retention",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda **_: care_plan_completion_summary(_care_plans()),
        ),
    ]


_DATA: dict[str, pd.DataFrame] = {}


def bind_data(tables: dict[str, pd.DataFrame]) -> None:
    global _DATA
    _DATA = tables


def _patients() -> pd.DataFrame:
    return _DATA["patients"]


def _care_plans() -> pd.DataFrame:
    return _DATA["care_plans"]
