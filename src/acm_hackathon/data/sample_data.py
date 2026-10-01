"""Synthetic chiropractic clinic datasets for local dev and demo ingestion."""

from __future__ import annotations

from datetime import date

import pandas as pd

from acm_hackathon.data.schemas import CarePlanStatus, LeadStatus


def patients_df() -> pd.DataFrame:
    rows = [
        ("P001", "Jordan Lee", "jordan@email.com", date(2025, 3, 1), 890.0, date(2026, 9, 10)),
        ("P002", "Sam Rivera", "sam@email.com", date(2025, 6, 15), 420.0, date(2026, 8, 2)),
        ("P003", "Alex Kim", "alex@email.com", date(2024, 11, 20), 1250.0, date(2026, 9, 28)),
        ("P004", "Taylor Brooks", "taylor@email.com", date(2026, 1, 5), 310.0, date(2026, 7, 15)),
        ("P005", "Casey Nguyen", "casey@email.com", date(2025, 9, 1), 680.0, None),
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "patient_id",
            "name",
            "email",
            "join_date",
            "lifetime_value",
            "last_visit_date",
        ],
    )


def leads_df() -> pd.DataFrame:
    rows = [
        ("L101", "Morgan Walsh", "google_ads", LeadStatus.NEW.value, date(2026, 9, 29), 150.0),
        ("L102", "Riley Chen", "referral", LeadStatus.CONTACTED.value, date(2026, 9, 27), 150.0),
        ("L103", "Jamie Ortiz", "instagram", LeadStatus.BOOKED.value, date(2026, 9, 25), 150.0),
        ("L104", "Drew Patel", "walk_in", LeadStatus.NEW.value, date(2026, 9, 30), 150.0),
        ("L105", "Quinn Adams", "google_ads", LeadStatus.LOST.value, date(2026, 9, 10), 0.0),
    ]
    return pd.DataFrame(
        rows,
        columns=["lead_id", "name", "source", "status", "created_date", "estimated_value"],
    )


def care_plans_df() -> pd.DataFrame:
    rows = [
        ("CP01", "P001", 12, 9, CarePlanStatus.ACTIVE.value, date(2026, 6, 1)),
        ("CP02", "P002", 8, 3, CarePlanStatus.ACTIVE.value, date(2026, 8, 1)),
        ("CP03", "P004", 6, 2, CarePlanStatus.ACTIVE.value, date(2026, 7, 1)),
        ("CP04", "P005", 10, 4, CarePlanStatus.DROPPED.value, date(2026, 4, 1)),
        ("CP05", "P003", 12, 12, CarePlanStatus.COMPLETED.value, date(2025, 12, 1)),
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "care_plan_id",
            "patient_id",
            "visits_prescribed",
            "visits_completed",
            "status",
            "start_date",
        ],
    )


def appointments_df() -> pd.DataFrame:
    rows = [
        ("A01", "P001", "adjustment", date(2026, 9, 10), 75.0, True),
        ("A02", "P002", "adjustment", date(2026, 8, 2), 75.0, True),
        ("A03", "P004", "rehab_session", date(2026, 7, 15), 95.0, True),
        ("A04", "P005", "adjustment", date(2026, 5, 20), 75.0, False),
        ("A05", "P003", "massage", date(2026, 9, 28), 110.0, True),
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "appointment_id",
            "patient_id",
            "service_id",
            "appointment_date",
            "revenue",
            "attended",
        ],
    )


def service_pricing_df() -> pd.DataFrame:
    rows = [
        ("initial_eval", "Initial Evaluation", 150.0, 0.55, 42),
        ("adjustment", "Chiropractic Adjustment", 75.0, 0.72, 128),
        ("rehab_session", "Rehab / Mobility Session", 95.0, 0.61, 56),
        ("massage", "Therapeutic Massage", 110.0, 0.48, 38),
    ]
    return pd.DataFrame(
        rows,
        columns=["service_id", "service_name", "price", "margin_pct", "monthly_volume"],
    )


def all_sample_tables() -> dict[str, pd.DataFrame]:
    return {
        "patients": patients_df(),
        "leads": leads_df(),
        "care_plans": care_plans_df(),
        "appointments": appointments_df(),
        "service_pricing": service_pricing_df(),
    }
