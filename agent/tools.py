"""
Agent tools — each function answers one business question using Spark SQL.

STEP EXPLANATION:
  Tool 1 → Leads      (stale pipeline)
  Tool 2 → Retention  (churn risk)
  Tool 3 → Pricing    (no-shows + package mix + marketing ROI)
  Tool 4 → Ranker     (merge + sort by $ impact) — in briefing.py
"""

from __future__ import annotations

from typing import Any


def _table(catalog: str, schema: str, name: str) -> str:
    return f"{catalog}.{schema}.{name}"


def find_stale_leads(spark: Any, catalog: str, schema: str, settings: dict) -> dict:
    """LEADS: open leads sitting too long without conversion."""
    econ = settings["economics"]
    days = settings["thresholds"]["stale_lead_days"]
    t = _table(catalog, schema, "leads")

    row = spark.sql(f"""
        SELECT
            COUNT(*) AS stale_count,
            SUM(CASE WHEN first_response_hours > {settings['thresholds']['slow_response_hours']}
                     THEN 1 ELSE 0 END) AS slow_response_count,
            ROUND(AVG(first_response_hours), 1) AS avg_response_hours
        FROM {t}
        WHERE status IN ('New', 'Contacted', 'Qualified')
          AND created_date <= date_sub(current_date(), {days})
    """).collect()[0]

    stale = int(row.stale_count or 0)
    impact = stale * econ["avg_initial_eval_revenue"] * econ["lead_conversion_rate"]

    return {
        "tool": "find_stale_leads",
        "focus": "leads",
        "metrics": {
            "stale_leads": stale,
            "slow_response_leads": int(row.slow_response_count or 0),
            "avg_response_hours": float(row.avg_response_hours or 0),
        },
        "estimated_impact_usd": round(impact, 2),
        "recommendation": (
            f"Same-day outreach to {stale:,} stale leads (open {days}+ days). "
            f"Prioritize Referral and Walk-In sources first."
        ),
    }


def find_churn_risk_patients(spark: Any, catalog: str, schema: str, settings: dict) -> dict:
    """RETENTION: active patients likely to churn."""
    econ = settings["economics"]
    threshold = settings["thresholds"]["high_churn_risk"]
    t = _table(catalog, schema, "patients")

    row = spark.sql(f"""
        SELECT
            COUNT(*) AS high_risk_count,
            ROUND(AVG(churn_risk_score), 3) AS avg_churn_score
        FROM {t}
        WHERE status = 'Active' AND churn_risk_score >= {threshold}
    """).collect()[0]

    count = int(row.high_risk_count or 0)
    per_patient = econ["avg_visit_revenue"] * econ["avg_recoverable_visits_per_reengaged_patient"]
    impact = count * per_patient * econ["churn_reengagement_rate"]

    return {
        "tool": "find_churn_risk_patients",
        "focus": "retention",
        "metrics": {
            "high_risk_active_patients": count,
            "avg_churn_score": float(row.avg_churn_score or 0),
            "churn_threshold": threshold,
        },
        "estimated_impact_usd": round(impact, 2),
        "recommendation": (
            f"Re-engagement campaign for {count:,} Active patients with churn risk ≥ {threshold:.0%}. "
            "Offer care-plan check-in + one promotional visit."
        ),
    }


def find_revenue_leaks(spark: Any, catalog: str, schema: str, settings: dict) -> dict:
    """PRICING: no-shows, package mix, and marketing waste."""
    econ = settings["economics"]
    appt = _table(catalog, schema, "appointments")
    visits = _table(catalog, schema, "visits")
    mkt = _table(catalog, schema, "marketing_campaigns")

    appt_row = spark.sql(f"""
        SELECT
            SUM(CASE WHEN status = 'No-Show' THEN 1 ELSE 0 END) AS no_shows,
            COUNT(*) AS total_appts
        FROM {appt}
    """).collect()[0]

    mix_row = spark.sql(f"""
        SELECT
            ROUND(100.0 * SUM(CASE WHEN payment_type = 'Package Plan' THEN 1 ELSE 0 END)
                  / COUNT(*), 1) AS package_plan_pct
        FROM {visits}
    """).collect()[0]

    mkt_row = spark.sql(f"""
        SELECT channel,
               ROUND(SUM(budget) / NULLIF(SUM(conversions), 0), 2) AS cost_per_conversion
        FROM {mkt}
        GROUP BY channel
        ORDER BY cost_per_conversion ASC
        LIMIT 1
    """).collect()[0]

    no_shows = int(appt_row.no_shows or 0)
    total = int(appt_row.total_appts or 1)
    no_show_rate = no_shows / total
    no_show_impact = no_shows * econ["avg_visit_revenue"] * 0.5  # recover half via reminders

    package_pct = float(mix_row.package_plan_pct or 0)
    package_gap_impact = 50_000 if package_pct < 20 else 20_000  # illustrative upsell opportunity

    best_channel = mkt_row.channel
    best_cpc = float(mkt_row.cost_per_conversion or 0)

    total_impact = no_show_impact + package_gap_impact

    return {
        "tool": "find_revenue_leaks",
        "focus": "pricing",
        "metrics": {
            "no_show_count": no_shows,
            "no_show_rate_pct": round(no_show_rate * 100, 1),
            "package_plan_pct": package_pct,
            "best_marketing_channel": best_channel,
            "best_cost_per_conversion": best_cpc,
        },
        "estimated_impact_usd": round(total_impact, 2),
        "recommendation": (
            f"No-show rate {no_show_rate:.1%} ({no_shows:,} appointments) — deploy SMS reminders. "
            f"Only {package_pct:.1f}% visits on Package Plan — upsell at visit 3. "
            f"Shift budget toward {best_channel} (${best_cpc:.0f}/conversion)."
        ),
    }


def find_top_lead_sources(spark: Any, catalog: str, schema: str, settings: dict) -> dict:
    """LEADS (bonus): best converting sources for today's calls."""
    t = _table(catalog, schema, "leads")
    rows = spark.sql(f"""
        SELECT source,
               COUNT(*) AS leads,
               ROUND(100.0 * SUM(CASE WHEN converted_flag THEN 1 ELSE 0 END) / COUNT(*), 1)
                   AS conversion_rate_pct
        FROM {t}
        WHERE status IN ('New', 'Contacted', 'Qualified')
        GROUP BY source
        ORDER BY conversion_rate_pct DESC
        LIMIT 3
    """).collect()

    top = [{"source": r.source, "leads": int(r.leads), "conversion_rate_pct": float(r.conversion_rate_pct)} for r in rows]
    econ = settings["economics"]
    open_leads = sum(r["leads"] for r in top)
    impact = open_leads * econ["avg_initial_eval_revenue"] * econ["lead_conversion_rate"] * 0.1

    return {
        "tool": "find_top_lead_sources",
        "focus": "leads",
        "metrics": {"top_sources": top, "open_leads_in_top_sources": open_leads},
        "estimated_impact_usd": round(impact, 2),
        "recommendation": (
            f"Call open leads from top sources first: {', '.join(r['source'] for r in top)}."
        ),
    }
