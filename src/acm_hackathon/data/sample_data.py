"""Minimal synthetic rows matching official hackathon schema — for local pytest only."""

from __future__ import annotations

from datetime import date

import pandas as pd


def all_sample_tables() -> dict[str, pd.DataFrame]:
    """Tables shaped like load_agent_tables_spark() output."""
    leads = pd.DataFrame(
        [
            ("LD0000001", "Referral", "LOC001", date(2026, 9, 29), "New", 4.0, 1, False, None),
            ("LD0000002", "Website Form", "LOC001", date(2026, 9, 20), "Contacted", 30.0, 3, False, None),
            ("LD0000003", "Walk-In", "LOC002", date(2026, 9, 25), "Qualified", 2.0, 4, False, None),
            ("LD0000004", "Social Media Ad", "LOC001", date(2026, 9, 28), "New", 48.0, 0, False, None),
            ("LD0000005", "Referral", "LOC002", date(2026, 8, 1), "Converted", 1.0, 6, True, "PT0000001"),
        ],
        columns=[
            "lead_id", "source", "assigned_location_id", "created_date", "status",
            "first_response_hours", "num_touchpoints", "converted_flag", "converted_patient_id",
        ],
    )

    patients = pd.DataFrame(
        [
            ("PT0000001", "LOC001", "Referral Program", date(2025, 3, 1), 18, "Active", "35-44", 42, 0.82),
            ("PT0000002", "LOC001", "Paid Ads", date(2025, 6, 15), 15, "Active", "25-34", 18, 0.71),
            ("PT0000003", "LOC002", "Organic Search", date(2024, 11, 20), 22, "Lapsed", "45-54", 55, 0.91),
            ("PT0000004", "LOC002", "Walk-In", date(2026, 1, 5), 8, "Active", "55-64", 9, 0.45),
            ("PT0000005", "LOC001", "Social Media", date(2025, 9, 1), 12, "Lapsed", "35-44", 14, 0.88),
        ],
        columns=[
            "patient_id", "home_location_id", "acquisition_source", "first_visit_date",
            "tenure_months", "status", "age_band", "lifetime_visit_count", "churn_risk_score",
        ],
    )

    patient_last_visit = pd.DataFrame(
        [
            ("PT0000001", date(2026, 9, 10)),
            ("PT0000002", date(2026, 8, 2)),
            ("PT0000003", date(2026, 4, 1)),
            ("PT0000004", date(2026, 7, 15)),
            ("PT0000005", date(2026, 3, 20)),
        ],
        columns=["patient_id", "last_visit_date"],
    )

    visit_summary = pd.DataFrame(
        [
            ("Spinal Adjustment", "Self-Pay", 120, 9000.0, 75.0),
            ("Spinal Adjustment", "Package Plan", 80, 4800.0, 60.0),
            ("Therapeutic Massage", "Self-Pay", 38, 4180.0, 110.0),
            ("Initial Consultation", "Insurance", 42, 6300.0, 150.0),
        ],
        columns=["service_type", "payment_type", "visit_count", "total_revenue", "avg_revenue"],
    )

    referrals = pd.DataFrame(
        [
            ("RF0000001", "PT0000001", "LD0000005", date(2026, 8, 1), "Verbal Referral", "Converted"),
            ("RF0000002", "PT0000003", None, date(2026, 7, 1), "Referral Card", "Pending"),
        ],
        columns=[
            "referral_id", "referring_patient_id", "referred_lead_id",
            "referral_date", "channel", "outcome",
        ],
    )

    marketing_campaigns = pd.DataFrame(
        [
            ("MKT0001", "Spring Spine Check", "Paid Search", date(2026, 3, 1), date(2026, 4, 1), 5000.0, 100000, 8000, 400, 80),
            ("MKT0002", "Local Wellness Event", "Local Event", date(2026, 6, 1), date(2026, 6, 15), 1200.0, 15000, 900, 45, 12),
        ],
        columns=[
            "campaign_id", "campaign_name", "channel", "start_date", "end_date",
            "budget", "impressions", "clicks", "leads_generated", "conversions",
        ],
    )

    no_show_summary = pd.DataFrame(
        [
            ("Completed", 740),
            ("No-Show", 100),
            ("Cancelled", 110),
            ("Rescheduled", 50),
        ],
        columns=["status", "appointment_count"],
    )

    return {
        "leads": leads,
        "patients": patients,
        "patient_last_visit": patient_last_visit,
        "visit_summary": visit_summary,
        "referrals": referrals,
        "marketing_campaigns": marketing_campaigns,
        "no_show_summary": no_show_summary,
    }
