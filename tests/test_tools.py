from datetime import date

from acm_hackathon.agents.tools.leads import analyze_lead_pipeline, score_lead_quality
from acm_hackathon.agents.tools.pricing import analyze_marketing_roi, analyze_visit_revenue
from acm_hackathon.agents.tools.retention import identify_at_risk_patients
from acm_hackathon.data.sample_data import all_sample_tables


def test_lead_pipeline_finds_stale():
    tables = all_sample_tables()
    result = analyze_lead_pipeline(tables["leads"], today=date(2026, 10, 1))
    assert result["focus_area"] == "leads"
    assert result["summary"]["total_leads"] == 5
    assert result["stale_lead_count"] >= 1


def test_lead_scoring_ranks_referrals():
    tables = all_sample_tables()
    result = score_lead_quality(tables["leads"])
    assert result["ranked_leads"][0]["source"] == "Referral"


def test_retention_finds_high_churn():
    tables = all_sample_tables()
    result = identify_at_risk_patients(
        tables["patients"],
        tables["patient_last_visit"],
        today=date(2026, 10, 1),
    )
    assert result["high_churn_count"] >= 1
    assert result["estimated_recoverable_revenue"] > 0


def test_visit_revenue_analysis():
    tables = all_sample_tables()
    result = analyze_visit_revenue(tables["visit_summary"])
    assert result["focus_area"] == "pricing"
    assert len(result["by_service"]) >= 1


def test_marketing_roi():
    tables = all_sample_tables()
    result = analyze_marketing_roi(tables["marketing_campaigns"])
    assert len(result["by_channel"]) >= 1
