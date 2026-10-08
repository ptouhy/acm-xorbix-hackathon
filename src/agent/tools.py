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


def _z_score(won_a: int, n_a: int, won_b: int, n_b: int) -> float:
    """Two-proportion z-test (a vs b). Small samples swing by several points on noise alone."""
    if not n_a or not n_b:
        return 0.0
    pooled = (won_a + won_b) / (n_a + n_b)
    se = (pooled * (1 - pooled) * (1 / n_a + 1 / n_b)) ** 0.5
    return (won_a / n_a - won_b / n_b) / se if se else 0.0


def find_stale_leads(spark: Any, catalog: str, schema: str, settings: dict) -> dict:
    """LEADS: open leads that went quiet — recent ones (worth a call) and dormant ones (win-back)."""
    econ = settings["economics"]
    th = settings["thresholds"]
    min_days, max_days, dormant_days = th["stale_lead_days"], th["stale_lead_max_days"], th["dormant_lead_max_days"]
    t = _table(catalog, schema, "leads")

    row = spark.sql(f"""
        SELECT
            SUM(CASE WHEN created_date <= date_sub(current_date(), {min_days})
                      AND created_date >= date_sub(current_date(), {max_days}) THEN 1 ELSE 0 END) AS stale_count,
            SUM(CASE WHEN created_date < date_sub(current_date(), {max_days}) THEN 1 ELSE 0 END) AS dormant_count,
            SUM(CASE WHEN created_date <= date_sub(current_date(), {min_days})
                      AND created_date >= date_sub(current_date(), {max_days})
                      AND first_response_hours > {th['slow_response_hours']} THEN 1 ELSE 0 END) AS slow_response_count,
            ROUND(AVG(CASE WHEN created_date <= date_sub(current_date(), {min_days})
                            AND created_date >= date_sub(current_date(), {max_days})
                           THEN first_response_hours END), 1) AS avg_response_hours
        FROM {t}
        WHERE status IN ('New', 'Contacted', 'Qualified')
          AND created_date >= date_sub(current_date(), {dormant_days})
    """).collect()[0]

    stale = int(row.stale_count or 0)
    dormant = int(row.dormant_count or 0)
    impact = (
        stale * econ["avg_initial_eval_revenue"] * econ["lead_conversion_rate"]
        + dormant * econ["avg_initial_eval_revenue"] * econ["dormant_lead_reactivation_rate"]
    )

    return {
        "tool": "find_stale_leads",
        "focus": "leads",
        "metrics": {
            "stale_leads": stale,
            "stale_window_days": f"{min_days}-{max_days}",
            "dormant_leads": dormant,
            "dormant_window_days": f"{max_days + 1}-{dormant_days}",
            "slow_response_leads": int(row.slow_response_count or 0),
            "avg_response_hours": float(row.avg_response_hours or 0),
        },
        "estimated_impact_usd": round(impact, 2),
        "recommendation": (
            f"Same-day outreach to {stale:,} leads that went quiet {min_days}-{max_days} days ago, "
            f"plus a win-back campaign for {dormant:,} dormant leads ({max_days + 1}-{dormant_days} days). "
            "Leads older than that are excluded as too cold to call."
        ),
    }


def _last_visit_cte(catalog: str, schema: str) -> str:
    return (f"SELECT patient_id, MAX(visit_date) AS last_visit, COUNT(*) AS visits "
            f"FROM {_table(catalog, schema, 'visits')} GROUP BY patient_id")


def find_churn_risk_patients(spark: Any, catalog: str, schema: str, settings: dict) -> dict:
    """RETENTION: Active patients who have stopped coming (last visit 60-180 days ago)."""
    econ = settings["economics"]
    th = settings["thresholds"]
    lo, hi = th["lapsing_min_days"], th["lapsing_max_days"]
    t = _table(catalog, schema, "patients")

    row = spark.sql(f"""
        SELECT COUNT(*) AS lapsing_count, ROUND(AVG(lv.visits), 1) AS avg_visits
        FROM {t} p JOIN ({_last_visit_cte(catalog, schema)}) lv ON lv.patient_id = p.patient_id
        WHERE p.status = 'Active'
          AND lv.last_visit <= date_sub(current_date(), {lo})
          AND lv.last_visit >= date_sub(current_date(), {hi})
    """).collect()[0]

    count = int(row.lapsing_count or 0)
    per_patient = econ["avg_visit_revenue"] * econ["avg_recoverable_visits_per_reengaged_patient"]
    impact = count * per_patient * econ["churn_reengagement_rate"]

    return {
        "tool": "find_churn_risk_patients",
        "focus": "retention",
        "metrics": {
            "lapsing_active_patients": count,
            "window_days": f"{lo}-{hi} since last visit",
            "avg_past_visits": float(row.avg_visits or 0),
        },
        "estimated_impact_usd": round(impact, 2),
        "recommendation": (
            f"Re-engage {count:,} Active patients whose last visit was {lo}-{hi} days ago "
            f"(they averaged {float(row.avg_visits or 0):.1f} past visits). "
            "Offer a care-plan check-in + one promotional visit."
        ),
    }


def find_revenue_leaks(spark: Any, catalog: str, schema: str, settings: dict) -> dict:
    """PRICING: no-show revenue loss (priced), plus package mix and marketing efficiency (observations)."""
    econ = settings["economics"]
    days = settings["thresholds"]["lookback_days"]
    appt = _table(catalog, schema, "appointments")
    visits = _table(catalog, schema, "visits")
    mkt = _table(catalog, schema, "marketing_campaigns")

    appt_row = spark.sql(f"""
        SELECT SUM(CASE WHEN status = 'No-Show' THEN 1 ELSE 0 END) AS no_shows, COUNT(*) AS total_appts
        FROM {appt}
        WHERE appointment_date >= date_sub(current_date(), {days})
    """).collect()[0]

    mix_row = spark.sql(f"""
        SELECT ROUND(100.0 * SUM(CASE WHEN payment_type = 'Package Plan' THEN 1 ELSE 0 END) / COUNT(*), 1)
                   AS package_plan_pct,
               ROUND(AVG(CASE WHEN payment_type = 'Package Plan' THEN revenue END), 2) AS package_rev,
               ROUND(AVG(CASE WHEN payment_type <> 'Package Plan' THEN revenue END), 2) AS other_rev
        FROM {visits}
        WHERE visit_date >= date_sub(current_date(), {days})
    """).collect()[0]

    channels = spark.sql(f"""
        SELECT channel, COUNT(*) AS campaigns,
               ROUND(SUM(budget) / NULLIF(SUM(conversions), 0), 2) AS cost_per_conversion
        FROM {mkt}
        GROUP BY channel
        ORDER BY cost_per_conversion ASC
    """).collect()

    no_shows = int(appt_row.no_shows or 0)
    total = int(appt_row.total_appts or 1)
    no_show_rate = no_shows / total
    lost = no_shows * econ["avg_visit_revenue"]
    impact = lost * econ["no_show_recovery_rate"]

    package_pct = float(mix_row.package_plan_pct or 0)
    package_rev, other_rev = float(mix_row.package_rev or 0), float(mix_row.other_rev or 0)
    best, worst = channels[0], channels[-1]

    return {
        "tool": "find_revenue_leaks",
        "focus": "pricing",
        "metrics": {
            "window_days": days,
            "no_show_count": no_shows,
            "no_show_rate_pct": round(no_show_rate * 100, 1),
            "no_show_revenue_lost_usd": round(lost, 2),
            "package_plan_pct": package_pct,
            "package_revenue_per_visit": package_rev,
            "other_revenue_per_visit": other_rev,
            "best_marketing_channel": best.channel,
            "best_cost_per_conversion": float(best.cost_per_conversion or 0),
            "worst_marketing_channel": worst.channel,
            "worst_cost_per_conversion": float(worst.cost_per_conversion or 0),
        },
        "estimated_impact_usd": round(impact, 2),
        "recommendation": (
            f"In the last {days} days {no_shows:,} appointments ({no_show_rate:.1%}) were no-shows, "
            f"about ${lost:,.0f} of lost revenue; reminders that win back {econ['no_show_recovery_rate']:.0%} "
            f"would return about ${impact:,.0f} a year. "
            f"Package Plan visits are {package_pct:.1f}% of volume and earn ${package_rev:.2f} vs "
            f"${other_rev:.2f} for other payment types, so no upsell revenue is counted. "
            f"Marketing: {best.channel} costs ${float(best.cost_per_conversion):.0f}/conversion vs "
            f"${float(worst.cost_per_conversion):.0f} for {worst.channel}; pilot a budget shift "
            "(not priced, since returns may not scale)."
        ),
    }


def find_top_lead_sources(spark: Any, catalog: str, schema: str, settings: dict) -> dict:
    """LEADS: do some lead sources win more often than others? (win rate = Converted / (Converted + Lost))"""
    econ = settings["economics"]
    th = settings["thresholds"]
    t = _table(catalog, schema, "leads")
    rows = spark.sql(f"""
        SELECT source,
               SUM(CASE WHEN status = 'Converted' THEN 1 ELSE 0 END) AS won,
               SUM(CASE WHEN status IN ('Converted', 'Lost') THEN 1 ELSE 0 END) AS resolved,
               SUM(CASE WHEN status IN ('New', 'Contacted', 'Qualified')
                         AND created_date >= date_sub(current_date(), {th['dormant_lead_max_days']})
                        THEN 1 ELSE 0 END) AS open_leads
        FROM {t}
        GROUP BY source
    """).collect()

    sources = [{
        "source": r.source,
        "win_rate_pct": round(100 * int(r.won or 0) / max(int(r.resolved or 0), 1), 1),
        "open_leads": int(r.open_leads or 0),
        "_won": int(r.won or 0),
        "_n": int(r.resolved or 0),
    } for r in rows]
    sources.sort(key=lambda x: x["win_rate_pct"], reverse=True)
    best, worst = sources[0], sources[-1]
    z = _z_score(best["_won"], best["_n"], worst["_won"], worst["_n"])
    significant = z >= th.get("min_z_score", 2.0)
    for x in sources:
        x.pop("_won"), x.pop("_n")

    if significant:
        top = sources[:3]
        impact = sum(x["open_leads"] for x in top) * econ["avg_initial_eval_revenue"] * econ["lead_conversion_rate"] * 0.1
        rec = (f"Work open leads from the highest-converting sources first: "
               f"{', '.join(x['source'] + ' (' + str(x['win_rate_pct']) + '%)' for x in top)}.")
    else:
        top, impact = sources[:3], 0.0
        rec = (f"No lead source stands out: win rates span only {best['win_rate_pct'] - worst['win_rate_pct']:.1f} pts "
               f"({worst['source']} {worst['win_rate_pct']}% to {best['source']} {best['win_rate_pct']}%, z={z:.1f}). "
               "Prioritize leads by age and status instead of source.")

    return {
        "tool": "find_top_lead_sources",
        "focus": "leads",
        "metrics": {"sources_by_win_rate": sources, "z_score": round(z, 2), "significant": significant},
        "estimated_impact_usd": round(impact, 2),
        "recommendation": rec,
    }


# --------------------------------------------------------------------------
# REASON tools — explain *why*. kind="diagnostic": not ranked as a $ action.
# ACT tool    — produce a concrete next step. kind="action": not ranked either.
# --------------------------------------------------------------------------


def diagnose_no_shows(spark: Any, catalog: str, schema: str, settings: dict, **_: Any) -> dict:
    """REASON: which segments have no-show rates above the clinic baseline?"""
    econ = settings["economics"]
    min_n = settings["thresholds"].get("min_segment_appts", 500)
    min_lift = settings["thresholds"].get("min_lift_pts", 1.0)
    t = _table(catalog, schema, "appointments")

    rows = spark.sql(f"""
        WITH a AS (
            SELECT appointment_type, booked_channel, location_id, status,
                   CASE WHEN lead_time_days <= 3 THEN 'booked 0-3 days out'
                        WHEN lead_time_days <= 7 THEN 'booked 4-7 days out'
                        WHEN lead_time_days <= 14 THEN 'booked 8-14 days out'
                        ELSE 'booked 15+ days out' END AS lead_bucket
            FROM {t}
        )
        SELECT 'appointment_type' AS dimension, appointment_type AS segment, COUNT(*) AS appts,
               SUM(CASE WHEN status = 'No-Show' THEN 1 ELSE 0 END) AS no_shows FROM a GROUP BY appointment_type
        UNION ALL
        SELECT 'booked_channel', booked_channel, COUNT(*),
               SUM(CASE WHEN status = 'No-Show' THEN 1 ELSE 0 END) FROM a GROUP BY booked_channel
        UNION ALL
        SELECT 'lead_time', lead_bucket, COUNT(*),
               SUM(CASE WHEN status = 'No-Show' THEN 1 ELSE 0 END) FROM a GROUP BY lead_bucket
        UNION ALL
        SELECT 'location', location_id, COUNT(*),
               SUM(CASE WHEN status = 'No-Show' THEN 1 ELSE 0 END) FROM a GROUP BY location_id
    """).collect()

    # Every dimension partitions the same appointments, so one of them gives the overall baseline.
    base = [r for r in rows if r.dimension == "appointment_type"]
    overall_rate = sum(int(r.no_shows or 0) for r in base) / max(sum(int(r.appts) for r in base), 1)

    segments = []
    for r in rows:
        appts, ns = int(r.appts), int(r.no_shows or 0)
        excess = ns - appts * overall_rate
        lift_pts = 100 * (ns / appts - overall_rate) if appts else 0
        if appts >= min_n and lift_pts >= min_lift:
            segments.append({
                "dimension": r.dimension,
                "segment": r.segment,
                "appointments": appts,
                "no_show_rate_pct": round(100 * ns / appts, 1),
                "excess_no_shows": round(excess),
            })
    segments.sort(key=lambda s: s["excess_no_shows"], reverse=True)
    top = segments[:5]

    recovery = econ.get("no_show_recovery_rate", 0.5)
    impact = sum(s["excess_no_shows"] for s in top[:3]) * econ["avg_visit_revenue"] * recovery
    baseline_pct = round(100 * overall_rate, 1)
    worst = "; ".join(
        f"{s['dimension']}={s['segment']} ({s['no_show_rate_pct']}% vs {baseline_pct}% baseline)"
        for s in top[:3]
    )

    return {
        "tool": "diagnose_no_shows",
        "kind": "diagnostic",
        "focus": "pricing",
        "metrics": {"baseline_no_show_rate_pct": baseline_pct, "highest_risk_segments": top},
        "estimated_impact_usd": round(impact, 2),
        "recommendation": (
            f"No-shows concentrate in: {worst}. Aim reminders, deposits or overbooking rules "
            "at these segments first."
            if top else (
                f"No segment is more than {min_lift} pt above the {baseline_pct}% baseline: "
                "no-shows are spread evenly, so segment targeting won't help. Use clinic-wide "
                "reminders instead."
            )
        ),
    }


def diagnose_lead_response(spark: Any, catalog: str, schema: str, settings: dict, **_: Any) -> dict:
    """REASON: does speed-to-lead change conversion?"""
    econ = settings["economics"]
    t = _table(catalog, schema, "leads")

    rows = spark.sql(f"""
        SELECT CASE WHEN first_response_hours < 1 THEN '<1h'
                    WHEN first_response_hours < 4 THEN '1-4h'
                    WHEN first_response_hours < 24 THEN '4-24h'
                    ELSE '24h+' END AS bucket,
               SUM(CASE WHEN status = 'Converted' THEN 1 ELSE 0 END) AS won,
               SUM(CASE WHEN status IN ('Converted', 'Lost') THEN 1 ELSE 0 END) AS resolved,
               SUM(CASE WHEN status IN ('New', 'Contacted', 'Qualified')
                         AND created_date >= date_sub(current_date(), {settings['thresholds']['dormant_lead_max_days']})
                        THEN 1 ELSE 0 END) AS open_leads
        FROM {t}
        GROUP BY 1
        ORDER BY MIN(first_response_hours)
    """).collect()

    buckets = []
    for r in rows:
        won, resolved = int(r.won or 0), int(r.resolved or 0)
        buckets.append({
            "first_response": r.bucket,
            "win_rate_pct": round(100 * won / resolved, 1) if resolved else 0.0,
            "resolved_leads": resolved,
            "open_leads": int(r.open_leads or 0),
            "_won": won,
        })

    usable = [b for b in buckets if b["resolved_leads"] > 0]
    best = max(usable, key=lambda b: b["win_rate_pct"])
    worst = min(usable, key=lambda b: b["win_rate_pct"])
    spread = round(best["win_rate_pct"] - worst["win_rate_pct"], 1)

    # Is best-vs-worst bigger than random variation? Small buckets (e.g. <1h) swing by several points on noise.
    n1, n2 = best["resolved_leads"], worst["resolved_leads"]
    z = _z_score(best["_won"], n1, worst["_won"], n2)
    min_z = settings["thresholds"].get("min_z_score", 2.0)
    significant = z >= min_z
    for b in buckets:
        b.pop("_won")

    if significant:
        gap_revenue = sum(
            b["open_leads"] * (best["win_rate_pct"] - b["win_rate_pct"]) / 100 for b in buckets
        ) * econ["avg_initial_eval_revenue"]
        rec = (f"Leads first answered in {best['first_response']} win {best['win_rate_pct']}% vs "
               f"{worst['first_response']} at {worst['win_rate_pct']}% (z={z:.1f}, statistically "
               "meaningful). Set a response-time SLA.")
    else:
        gap_revenue = 0.0
        rec = (f"No statistically meaningful link between response speed and win rate (best "
               f"{best['first_response']} {best['win_rate_pct']}% vs worst {worst['first_response']} "
               f"{worst['win_rate_pct']}%, z={z:.1f}, need >= {min_z}). The gap is within random "
               "variation, so don't build an SLA on it; prioritize follow-up volume and source quality.")

    return {
        "tool": "diagnose_lead_response",
        "kind": "diagnostic",
        "focus": "leads",
        "metrics": {"win_rate_by_first_response": buckets, "spread_pts": spread,
                    "z_score": round(z, 2), "significant": significant},
        "estimated_impact_usd": round(gap_revenue, 2),
        "recommendation": rec,
    }


_OPEN_STATUSES = "('New', 'Contacted', 'Qualified')"

_MESSAGES = {
    "stale_leads": (
        "Hi {first_name}, it's {clinic_name} following up on your inquiry. We have openings "
        "this week for an initial consultation. Want us to hold a spot? Reply YES to confirm."
    ),
    "churn_risk_patients": (
        "Hi {first_name}, we've missed you at {clinic_name}! Let's get your care plan back on "
        "track. Book a check-in this week and your next visit is on us. Reply YES to schedule."
    ),
}


QUEUE_TABLE = "outreach_queue"
QUEUE_DDL = "batch_id STRING, queued_at TIMESTAMP, segment STRING, target_id STRING, message_template STRING, status STRING"


def _stage_in_queue(spark: Any, catalog: str, schema: str, settings: dict, segment: str,
                    targets: list[dict], message: str) -> dict:
    """ACTION: write the call list to outreach_queue as 'pending_approval'. People already pending are skipped."""
    if not settings["agent"].get("stage_outreach", True) or not targets:
        return {"staged": False}
    import uuid
    from datetime import datetime, timezone

    try:
        table = _table(catalog, schema, QUEUE_TABLE)
        ids = [t.get("lead_id") or t.get("patient_id") for t in targets]
        pending: set[str] = set()
        if spark.catalog.tableExists(table):
            pending = {r.target_id for r in spark.sql(
                f"SELECT target_id FROM {table} WHERE status = 'pending_approval' AND segment = '{segment}'").collect()}
        new_ids = [i for i in ids if i not in pending]
        batch_id = uuid.uuid4().hex[:12]
        if new_ids:
            now = datetime.now(timezone.utc)
            rows = [(batch_id, now, segment, i, message, "pending_approval") for i in new_ids]
            spark.createDataFrame(rows, schema=QUEUE_DDL).write.format("delta").mode("append").saveAsTable(table)
        return {"staged": True, "batch_id": batch_id, "status": "pending_approval",
                "newly_staged": len(new_ids), "already_pending": len(ids) - len(new_ids), "table": table}
    except Exception as exc:  # staging must never break the briefing
        return {"staged": False, "error": f"{type(exc).__name__}: {exc}"}


def draft_outreach(
    spark: Any, catalog: str, schema: str, settings: dict,
    segment: str | None = None, limit: int = 10, **_: Any,
) -> dict:
    """ACT: prioritized contact list + message template for a segment, staged for approval (synthetic IDs only)."""
    econ = settings["economics"]
    limit = max(1, min(int(limit or 10), 25))

    if segment == "stale_leads":
        th = settings["thresholds"]
        t = _table(catalog, schema, "leads")
        where = (f"status IN {_OPEN_STATUSES} AND created_date <= date_sub(current_date(), {th['stale_lead_days']})"
                 f" AND created_date >= date_sub(current_date(), {th['stale_lead_max_days']})")
        total = int(spark.sql(f"SELECT COUNT(*) AS n FROM {t} WHERE {where}").collect()[0].n)
        rows = spark.sql(f"""
            SELECT lead_id, source, assigned_location_id AS location_id, created_date, status, num_touchpoints
            FROM {t} WHERE {where}
            ORDER BY CASE status WHEN 'Qualified' THEN 0 WHEN 'Contacted' THEN 1 ELSE 2 END,
                     num_touchpoints DESC, created_date DESC
            LIMIT {limit * 2}
        """).collect()
        # Next-in-line people (same size, next priority) are the holdout: NOT contacted, tracked
        # so measure_outcomes can compare them with the contacted group later.
        holdout_ids = [r.lead_id for r in rows[limit:]]
        rows = rows[:limit]
        targets = [{
            "lead_id": r.lead_id, "source": r.source, "location_id": r.location_id,
            "created_date": str(r.created_date), "status": r.status,
            "touchpoints": int(r.num_touchpoints),
        } for r in rows]
        impact = len(targets) * econ["avg_initial_eval_revenue"] * econ["lead_conversion_rate"]
        focus, why = "leads", "Qualified and warmest (most touchpoints) leads first."

    elif segment == "churn_risk_patients":
        th = settings["thresholds"]
        lo, hi = th["lapsing_min_days"], th["lapsing_max_days"]
        t = _table(catalog, schema, "patients")
        src = (f"{t} p JOIN ({_last_visit_cte(catalog, schema)}) lv ON lv.patient_id = p.patient_id "
               f"WHERE p.status = 'Active' AND lv.last_visit <= date_sub(current_date(), {lo}) "
               f"AND lv.last_visit >= date_sub(current_date(), {hi})")
        total = int(spark.sql(f"SELECT COUNT(*) AS n FROM {src}").collect()[0].n)
        rows = spark.sql(f"""
            SELECT p.patient_id, p.home_location_id AS location_id, p.tenure_months,
                   lv.visits AS past_visits, lv.last_visit
            FROM {src}
            ORDER BY lv.visits DESC, lv.last_visit DESC
            LIMIT {limit * 2}
        """).collect()
        holdout_ids = [r.patient_id for r in rows[limit:]]
        rows = rows[:limit]
        targets = [{
            "patient_id": r.patient_id, "location_id": r.location_id,
            "tenure_months": int(r.tenure_months),
            "past_visits": int(r.past_visits),
            "last_visit": str(r.last_visit),
        } for r in rows]
        per_patient = econ["avg_visit_revenue"] * econ["avg_recoverable_visits_per_reengaged_patient"]
        impact = len(targets) * per_patient * econ["churn_reengagement_rate"]
        focus, why = "retention", "Most loyal (most past visits) first."

    else:
        raise ValueError("segment must be 'stale_leads' or 'churn_risk_patients'")

    queue = _stage_in_queue(spark, catalog, schema, settings, segment, targets, _MESSAGES[segment])

    return {
        "tool": "draft_outreach",
        "kind": "action",
        "focus": focus,
        "metrics": {"segment": segment, "segment_size": total, "batch_size": len(targets)},
        "queue": queue,
        "targets": targets,
        "holdout_ids": holdout_ids,
        "message_template": _MESSAGES[segment],
        "estimated_impact_usd": round(impact, 2),
        "recommendation": (
            f"Contact these {len(targets)} of {total:,} {segment.replace('_', ' ')} today. {why} "
            + (f"Staged {queue['newly_staged']} in outreach_queue (status: pending_approval)." if queue.get("staged") else "")
        ),
    }
