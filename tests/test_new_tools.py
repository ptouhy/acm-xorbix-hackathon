"""Reason/Act tool tests with a fake Spark session (no cluster needed)."""

from types import SimpleNamespace as NS

import pytest

from agent.briefing import rank_actions
from agent.settings import load_settings
from agent.tools import diagnose_lead_response, diagnose_no_shows, draft_outreach


class FakeSpark:
    """Returns canned rows for the first registered substring found in the SQL."""

    def __init__(self, responses):
        self.responses = responses
        self.queries = []

    def sql(self, q):
        self.queries.append(q)
        for needle, rows in self.responses.items():
            if needle in q:
                return NS(collect=lambda rows=rows: rows)
        raise AssertionError(f"unexpected query: {q[:80]}")


S = load_settings()


def test_diagnose_no_shows_flags_segments_above_baseline():
    rows = [
        NS(dimension="appointment_type", segment="Massage", appts=1000, no_shows=200),
        NS(dimension="appointment_type", segment="Adjustment", appts=1000, no_shows=100),
        NS(dimension="booked_channel", segment="Phone", appts=2000, no_shows=300),
        NS(dimension="location", segment="LOC001", appts=100, no_shows=90),  # below min volume
    ]
    out = diagnose_no_shows(FakeSpark({"WITH a AS": rows}), "c", "s", S)
    assert out["kind"] == "diagnostic"
    assert out["metrics"]["baseline_no_show_rate_pct"] == 15.0
    top = out["metrics"]["highest_risk_segments"]
    assert top[0]["segment"] == "Massage"  # 200 vs 150 expected
    assert all(s["appointments"] >= 500 for s in top)
    assert out["estimated_impact_usd"] > 0


def test_diagnose_no_shows_says_so_when_nothing_stands_out():
    rows = [
        NS(dimension="appointment_type", segment="A", appts=1000, no_shows=100),
        NS(dimension="appointment_type", segment="B", appts=1000, no_shows=102),  # +0.2 pt: noise
    ]
    out = diagnose_no_shows(FakeSpark({"WITH a AS": rows}), "c", "s", S)
    assert out["metrics"]["highest_risk_segments"] == []
    assert out["estimated_impact_usd"] == 0
    assert "spread evenly" in out["recommendation"]


def test_diagnose_lead_response_reports_flat_effect_honestly():
    rows = [
        NS(bucket="<1h", won=60, resolved=100, open_leads=10),
        NS(bucket="24h+", won=61, resolved=100, open_leads=10),
    ]
    out = diagnose_lead_response(FakeSpark({"first_response_hours": rows}), "c", "s", S)
    assert out["metrics"]["spread_pts"] == 1.0
    assert "barely moves" in out["recommendation"]


def test_draft_outreach_stale_leads_returns_targets_and_template():
    spark = FakeSpark({
        "COUNT(*)": [NS(n=26000)],
        "ORDER BY": [NS(lead_id="LD1", source="Referral", location_id="LOC001",
                        created_date="2026-09-01", status="Qualified", num_touchpoints=5)],
    })
    out = draft_outreach(spark, "c", "s", S, segment="stale_leads", limit=500)
    assert out["kind"] == "action"
    assert out["metrics"]["segment_size"] == 26000
    assert out["targets"][0]["lead_id"] == "LD1"
    assert "{first_name}" in out["message_template"]
    assert "LIMIT 25" in spark.queries[-1]  # limit is clamped


def test_draft_outreach_rejects_unknown_segment():
    with pytest.raises(ValueError):
        draft_outreach(FakeSpark({}), "c", "s", S, segment="everyone")


def test_rank_actions_ignores_diagnostic_and_action_results():
    results = [
        {"tool": "a", "focus": "leads", "estimated_impact_usd": 100, "recommendation": "A"},
        {"tool": "d", "kind": "diagnostic", "focus": "pricing", "estimated_impact_usd": 9999, "recommendation": "D"},
        {"tool": "x", "kind": "action", "focus": "leads", "estimated_impact_usd": 9999, "recommendation": "X"},
    ]
    assert [a["tool"] for a in rank_actions(results)] == ["a"]
