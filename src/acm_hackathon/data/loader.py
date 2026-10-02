"""Load hackathon tables from Unity Catalog (Spark) for agent tools."""

from __future__ import annotations

from typing import Any

import pandas as pd

from acm_hackathon.settings import DatabricksSettings

# Tables passed to agent tools — aggregated or filtered to stay within serverless memory.
AGENT_TABLE_KEYS = (
    "leads",
    "patients",
    "patient_last_visit",
    "visit_summary",
    "referrals",
    "marketing_campaigns",
    "no_show_summary",
)


def _fqn(catalog: str, schema: str, table: str) -> str:
    return f"{catalog}.{schema}.{table}"


def load_agent_tables_spark(spark: Any, catalog: str | None = None, schema: str | None = None) -> dict[str, pd.DataFrame]:
    """Load filtered/aggregated tables from Unity Catalog via Spark SQL."""
    settings = DatabricksSettings.load()
    catalog = catalog or settings.catalog
    schema = schema or settings.schema
    p = f"{catalog}.{schema}"

    leads = spark.sql(
        f"""
        SELECT *
        FROM {_fqn(catalog, schema, 'leads')}
        WHERE created_date >= date_sub(current_date(), 120)
        """
    ).toPandas()

    patients = spark.sql(
        f"""
        SELECT patient_id, home_location_id, acquisition_source, first_visit_date,
               tenure_months, status, age_band, lifetime_visit_count, churn_risk_score
        FROM {_fqn(catalog, schema, 'patients')}
        WHERE status IN ('Active', 'Lapsed')
           OR churn_risk_score >= 0.65
        """
    ).toPandas()

    patient_last_visit = spark.sql(
        f"""
        SELECT patient_id, MAX(visit_date) AS last_visit_date
        FROM {_fqn(catalog, schema, 'visits')}
        GROUP BY patient_id
        """
    ).toPandas()

    visit_summary = spark.sql(
        f"""
        SELECT service_type, payment_type,
               COUNT(*) AS visit_count,
               SUM(revenue) AS total_revenue,
               AVG(revenue) AS avg_revenue
        FROM {_fqn(catalog, schema, 'visits')}
        GROUP BY service_type, payment_type
        """
    ).toPandas()

    referrals = spark.sql(
        f"""
        SELECT *
        FROM {_fqn(catalog, schema, 'referrals')}
        WHERE referral_date >= date_sub(current_date(), 365)
        """
    ).toPandas()

    marketing_campaigns = spark.sql(
        f"""
        SELECT *
        FROM {_fqn(catalog, schema, 'marketing_campaigns')}
        WHERE end_date >= date_sub(current_date(), 365)
        """
    ).toPandas()

    no_show_summary = spark.sql(
        f"""
        SELECT status, COUNT(*) AS appointment_count
        FROM {_fqn(catalog, schema, 'appointments')}
        GROUP BY status
        """
    ).toPandas()

    return {
        "leads": leads,
        "patients": patients,
        "patient_last_visit": patient_last_visit,
        "visit_summary": visit_summary,
        "referrals": referrals,
        "marketing_campaigns": marketing_campaigns,
        "no_show_summary": no_show_summary,
    }


def validate_tables_exist(spark: Any, catalog: str, schema: str) -> list[str]:
    """Return list of missing table names."""
    settings = DatabricksSettings.load()
    missing = []
    for key in settings.tables:
        table = settings.tables[key]
        fqn = _fqn(catalog, schema, table)
        if not spark.catalog.tableExists(fqn):
            missing.append(fqn)
    return missing
