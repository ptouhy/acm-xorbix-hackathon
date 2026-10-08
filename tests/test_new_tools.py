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


def test_diagnose_lead_response_rejects_small_bucket_noise():
    # 5-pt gap, but the fast bucket has only 190 resolved leads -> within random variation
    rows = [
        NS(bucket="<1h", won=129, resolved=190, open_leads=5),
        NS(bucket="24h+", won=8500, resolved=13500, open_leads=500),
    ]
    out = diagnose_lead_response(FakeSpark({"first_response_hours": rows}), "c", "s", S)
    assert out["metrics"]["significant"] is False
    assert out["estimated_impact_usd"] == 0
    assert "No statistically meaningful" in out["recommendation"]


def test_diagnose_lead_response_reports_real_effect():
    rows = [
        NS(bucket="<1h", won=7000, resolved=10000, open_leads=100),
        NS(bucket="24h+", won=5000, resolved=10000, open_leads=100),
    ]
    out = diagnose_lead_response(FakeSpark({"first_response_hours": rows}), "c", "s", S)
    assert out["metrics"]["significant"] is True
    assert out["estimated_impact_usd"] > 0
    assert "response-time SLA" in out["recommendation"]


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
    assert "LIMIT 50" in spark.queries[-1]  # limit clamped to 25 targets + 25 holdout


def test_draft_outreach_splits_targets_from_holdout():
    rows = [NS(lead_id=f"L{i}", source="x", location_id="LOC1", created_date="2026-09-01",
               status="Qualified", num_touchpoints=3) for i in range(4)]
    spark = FakeSpark({"COUNT(*)": [NS(n=100)], "ORDER BY": rows})
    out = draft_outreach(spark, "c", "s", S, segment="stale_leads", limit=2)
    assert [t["lead_id"] for t in out["targets"]] == ["L0", "L1"]
    assert out["holdout_ids"] == ["L2", "L3"]


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


# ---- Measure ----------------------------------------------------------------

from datetime import datetime, timedelta, timezone  # noqa: E402

from agent.briefing import BriefingResult  # noqa: E402
from agent.measure import measure_outcomes  # noqa: E402
from agent.tracking import ledger_rows, log_run  # noqa: E402

NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)


def test_ledger_rows_include_contacted_and_holdout():
    out = {"tool": "draft_outreach", "estimated_impact_usd": 300.0,
           "metrics": {"segment": "stale_leads"},
           "targets": [{"lead_id": "L1"}, {"lead_id": "L2"}], "holdout_ids": ["L3", "L4"]}
    rows = ledger_rows("run1", "q", [out, {"tool": "find_stale_leads"}], NOW)
    assert [(r[4], r[5]) for r in rows] == [("contacted", "L1"), ("contacted", "L2"), ("holdout", "L3"), ("holdout", "L4")]
    assert rows[0][6] == 150.0 and rows[2][6] == 0.0


def _measure_rows(created):
    return [
        NS(run_id="r1", cohort="contacted", created_at=created, n=10, outcomes=4, expected_usd=300.0),
        NS(run_id="r1", cohort="holdout", created_at=created, n=10, outcomes=2, expected_usd=0.0),
    ]


def test_measure_handles_naive_spark_datetimes():
    spark = FakeSpark({"r.segment = 'stale_leads'": _measure_rows((NOW - timedelta(days=10)).replace(tzinfo=None))})
    spark.responses["r.segment = 'churn_risk_patients'"] = []
    assert measure_outcomes(spark, "c", "s", S, now=NOW)[0]["days_since"] == 10


def test_measure_reports_lift_after_followup_window():
    spark = FakeSpark({"r.segment = 'stale_leads'": _measure_rows(NOW - timedelta(days=10))})
    spark.responses["r.segment = 'churn_risk_patients'"] = []
    res = measure_outcomes(spark, "c", "s", S, now=NOW)
    assert res[0]["lift_pts"] == 20.0 and "outperformed" in res[0]["verdict"]


def test_measure_only_reports_baseline_before_followup_window():
    spark = FakeSpark({"r.segment = 'stale_leads'": _measure_rows(NOW - timedelta(days=1))})
    spark.responses["r.segment = 'churn_risk_patients'"] = []
    res = measure_outcomes(spark, "c", "s", S, now=NOW)
    assert "Baseline captured" in res[0]["verdict"]


def test_log_run_is_non_fatal_without_mlflow(monkeypatch, capsys):
    monkeypatch.setitem(__import__("sys").modules, "mlflow", None)  # import raises ImportError
    run_id = log_run(BriefingResult(question="q"), "/x", "c", "s", 1.0)
    assert len(run_id) == 32 and "non-fatal" in capsys.readouterr().out
