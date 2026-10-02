"""Patient retention tools — official chiro_hackathon patients + visits schema."""

from __future__ import annotations

from datetime import date

import pandas as pd

from acm_hackathon.agents.tools.base import ToolDefinition


def identify_at_risk_patients(
    patients: pd.DataFrame,
    patient_last_visit: pd.DataFrame,
    today: date | None = None,
    churn_threshold: float = 0.65,
    inactive_days: int = 90,
) -> dict:
    """Find high churn-risk and inactive patients with estimated recoverable revenue."""
    today = today or date.today()
    p = patients.merge(patient_last_visit, on="patient_id", how="left")
    p["last_visit_date"] = pd.to_datetime(p["last_visit_date"])
    p["days_since_visit"] = p["last_visit_date"].apply(
        lambda d: (today - d.date()).days if pd.notna(d) else 999
    )

    high_churn = p[(p["churn_risk_score"] >= churn_threshold) & (p["status"] == "Active")]
    inactive = p[p["days_since_visit"] >= inactive_days]
    lapsed = p[p["status"] == "Lapsed"]

    # Rough LTV recovery estimate: avg visit revenue $75 × expected 4 visits if re-engaged
    avg_recovery_per_patient = 300.0
    at_risk_count = len(pd.concat([high_churn, inactive, lapsed]).drop_duplicates("patient_id"))
    recoverable_revenue = at_risk_count * avg_recovery_per_patient

    recommendations = []
    if len(high_churn):
        recommendations.append(
            f"Outreach to {len(high_churn):,} Active patients with churn risk ≥ {churn_threshold:.0%}."
        )
    if len(inactive):
        recommendations.append(
            f"Re-engagement campaign for {len(inactive):,} patients inactive {inactive_days}+ days."
        )
    if len(lapsed):
        recommendations.append(
            f"Win-back offers for {len(lapsed):,} Lapsed patients — care-plan reminder + promo visit."
        )
    recommendations.append(
        f"Estimated recoverable revenue if 25% re-engage: ${recoverable_revenue * 0.25:,.0f}."
    )

    sample_cols = ["patient_id", "status", "churn_risk_score", "days_since_visit", "lifetime_visit_count"]
    return {
        "focus_area": "retention",
        "high_churn_count": len(high_churn),
        "inactive_count": len(inactive),
        "lapsed_count": len(lapsed),
        "at_risk_sample": p.nlargest(10, "churn_risk_score")[sample_cols].to_dict(orient="records"),
        "estimated_recoverable_revenue": round(recoverable_revenue, 2),
        "recommendations": recommendations,
    }


def appointment_attendance_summary(no_show_summary: pd.DataFrame) -> dict:
    """Summarize no-show and cancellation rates."""
    total = int(no_show_summary["appointment_count"].sum())
    by_status = no_show_summary.set_index("status")["appointment_count"].to_dict()
    no_shows = by_status.get("No-Show", 0)
    cancelled = by_status.get("Cancelled", 0)
    no_show_rate = no_shows / total if total else 0

    recommendations = [
        f"No-show rate: {no_show_rate:.1%} ({no_shows:,} of {total:,} appointments).",
        "Send SMS reminders 24h before appointment; offer easy reschedule link.",
    ]
    if cancelled:
        recommendations.append(
            f"{cancelled:,} cancellations — follow up within 48h to rebook."
        )

    return {
        "focus_area": "retention",
        "by_status": by_status,
        "no_show_rate": round(no_show_rate, 4),
        "recommendations": recommendations,
    }


def get_retention_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="identify_at_risk_patients",
            description="Find high churn-risk, inactive, and lapsed patients with revenue impact.",
            focus_area="retention",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda **_: identify_at_risk_patients(_data("patients"), _data("patient_last_visit")),
        ),
        ToolDefinition(
            name="appointment_attendance_summary",
            description="Summarize no-show and cancellation rates.",
            focus_area="retention",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda **_: appointment_attendance_summary(_data("no_show_summary")),
        ),
    ]


_DATA: dict[str, pd.DataFrame] = {}


def bind_data(tables: dict[str, pd.DataFrame]) -> None:
    global _DATA
    _DATA = tables


def _data(key: str) -> pd.DataFrame:
    if key not in _DATA:
        raise RuntimeError(f"Retention tools require '{key}' — bind_data() first.")
    return _DATA[key]
