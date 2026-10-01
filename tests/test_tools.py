from datetime import date

from acm_hackathon.agents.tools.leads import analyze_lead_pipeline, score_lead_quality
from acm_hackathon.agents.tools.pricing import analyze_service_margins, recommend_membership_offers
from acm_hackathon.agents.tools.retention import identify_at_risk_patients
from acm_hackathon.data.sample_data import all_sample_tables


def test_lead_pipeline_finds_stale():
    tables = all_sample_tables()
    result = analyze_lead_pipeline(tables["leads"], today=date(2026, 10, 1))
    assert result["focus_area"] == "leads"
    assert result["summary"]["total_leads"] == 5
    assert len(result["recommendations"]) >= 1


def test_lead_scoring_ranks_referrals():
    tables = all_sample_tables()
    result = score_lead_quality(tables["leads"])
    assert result["ranked_leads"][0]["source"] == "referral"


def test_retention_finds_inactive():
    tables = all_sample_tables()
    result = identify_at_risk_patients(
        tables["patients"], tables["care_plans"], today=date(2026, 10, 1)
    )
    inactive_ids = {p["patient_id"] for p in result["inactive_patients"]}
    assert "P005" in inactive_ids


def test_pricing_margins():
    tables = all_sample_tables()
    result = analyze_service_margins(tables["service_pricing"])
    assert result["focus_area"] == "pricing"
    assert len(result["services"]) == 4
    assert len(result["recommendations"]) >= 1


def test_membership_offers():
    tables = all_sample_tables()
    memberships = [{"id": "w4", "name": "Wellness 4", "visits": 4, "price": 260}]
    result = recommend_membership_offers(tables["service_pricing"], memberships)
    assert result["membership_offers"][0]["savings_vs_single"] > 0
