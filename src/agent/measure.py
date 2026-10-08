"""
Measure (part 2) — did the recommended outreach work?

STEP EXPLANATION:
  For every recorded batch we compare the people the agent said to contact against the
  holdout (next-in-line, same size, NOT contacted):
    stale_leads          -> outcome = lead converted
    churn_risk_patients  -> outcome = patient has a visit after the recommendation
  lift = contacted rate - holdout rate. Outcomes are only judged after min_followup_days;
  before that we report the baseline. Re-run after the outreach window to get a verdict.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agent.settings import load_settings
from agent.tracking import LEDGER_TABLE

# segment -> (source relation, key column, outcome expression, where {c}/{s} = catalog/schema)
_OUTCOME_SQL = {
    "stale_leads": ("{c}.{s}.leads", "lead_id", "CASE WHEN x.converted_flag THEN 1 ELSE 0 END"),
    # outcome = the patient came back: has a visit after the recommendation
    "churn_risk_patients": (
        "(SELECT patient_id, MAX(visit_date) AS last_visit FROM {c}.{s}.visits GROUP BY patient_id)",
        "patient_id",
        "CASE WHEN x.last_visit > to_date(r.created_at) THEN 1 ELSE 0 END",
    ),
}


def measure_outcomes(spark: Any, catalog: str, schema: str, settings: dict | None = None,
                     now: datetime | None = None) -> list[dict]:
    settings = settings or load_settings()
    min_days = settings["thresholds"].get("min_followup_days", 7)
    now = (now or datetime.now(timezone.utc)).replace(tzinfo=None)  # Spark returns naive UTC datetimes
    ledger = f"{catalog}.{schema}.{LEDGER_TABLE}"

    results = []
    for segment, (table, key, outcome) in _OUTCOME_SQL.items():
        rows = spark.sql(f"""
            SELECT r.run_id, r.cohort, MIN(r.created_at) AS created_at, COUNT(*) AS n,
                   SUM({outcome}) AS outcomes, SUM(r.expected_impact_usd) AS expected_usd
            FROM {ledger} r LEFT JOIN {table.format(c=catalog, s=schema)} x ON x.{key} = r.target_id
            WHERE r.segment = '{segment}'
            GROUP BY r.run_id, r.cohort
        """).collect()

        by_run: dict[str, dict] = {}
        for r in rows:
            d = by_run.setdefault(r.run_id, {"created_at": r.created_at})
            d[r.cohort] = {"n": int(r.n), "outcomes": int(r.outcomes or 0), "expected_usd": float(r.expected_usd or 0)}

        for run_id, d in by_run.items():
            c, h = d.get("contacted"), d.get("holdout")
            if not c:
                continue
            days = max((now - d["created_at"].replace(tzinfo=None)).days, 0)
            c_rate = 100 * c["outcomes"] / c["n"]
            h_rate = 100 * h["outcomes"] / h["n"] if h and h["n"] else None
            lift = round(c_rate - h_rate, 1) if h_rate is not None else None
            if days < min_days:
                verdict = f"Baseline captured {days}d ago. Re-run after {min_days} days of outreach."
            elif lift is None:
                verdict = "No holdout recorded; cannot judge."
            elif lift > 0:
                verdict = f"Contacted group outperformed holdout by {lift} pts."
            else:
                verdict = f"No lift vs holdout ({lift} pts). Revisit targeting or message."
            results.append({
                "run_id": run_id,
                "segment": segment,
                "days_since": days,
                "contacted_n": c["n"],
                "contacted_rate_pct": round(c_rate, 1),
                "holdout_n": h["n"] if h else 0,
                "holdout_rate_pct": round(h_rate, 1) if h_rate is not None else None,
                "lift_pts": lift,
                "expected_impact_usd": round(c["expected_usd"], 2),
                "verdict": verdict,
            })
    return sorted(results, key=lambda r: r["days_since"])
