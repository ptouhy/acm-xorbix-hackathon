"""
Measure (part 1) — log every run to MLflow and record who the agent told staff to contact.

STEP EXPLANATION:
  MLflow answers "what did the agent do?" (question, tools, impact, trace).
  The ledger table (agent_recommendations) answers "did it work?" later: it stores each
  contacted person AND a same-size holdout group, so src/agent/measure.py can compare outcomes.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from agent.briefing import BriefingResult

LEDGER_TABLE = "agent_recommendations"
LEDGER_DDL = (
    "run_id STRING, created_at TIMESTAMP, question STRING, segment STRING, "
    "cohort STRING, target_id STRING, expected_impact_usd DOUBLE"
)


def log_run(result: BriefingResult, experiment_path: str, catalog: str, schema: str,
            duration_s: float) -> str:
    """Log one agent run to MLflow. Returns the run id (a local uuid if MLflow is unavailable)."""
    try:
        import mlflow  # lazy: only needed on Databricks / when logging

        mlflow.set_experiment(experiment_path)
        with mlflow.start_run(run_name="briefing") as run:
            mlflow.log_params({
                "question": result.question[:250],
                "mode": result.mode,
                "catalog": catalog,
                "schema": schema,
                "tools_used": ",".join(t["tool"] for t in result.tool_outputs)[:250],
            })
            mlflow.log_metrics({
                "total_estimated_impact_usd": result.total_estimated_impact_usd,
                "tool_calls": len([t for t in result.trace if t["type"] == "tool_call"]),
                "duration_s": round(duration_s, 2),
                "used_fallback": 0.0 if result.mode == "agentic" else 1.0,
            })
            mlflow.log_text(result.briefing_text, "briefing.md")
            mlflow.log_dict(json.loads(json.dumps(result.trace, default=str)), "trace.json")
            return run.info.run_id
    except Exception as exc:  # observability must never break the agent
        print(f"MLflow logging skipped (non-fatal): {exc}")
        return uuid.uuid4().hex


def ledger_rows(run_id: str, question: str, outputs: list[dict], now: datetime) -> list[tuple]:
    """One row per contacted person and per holdout person, for every draft_outreach batch."""
    rows = []
    for o in outputs:
        if o.get("tool") != "draft_outreach":
            continue
        segment = o["metrics"]["segment"]
        per_person = o["estimated_impact_usd"] / max(len(o["targets"]), 1)
        for t in o["targets"]:
            rows.append((run_id, now, question, segment, "contacted",
                         t.get("lead_id") or t.get("patient_id"), per_person))
        for pid in o.get("holdout_ids", []):
            rows.append((run_id, now, question, segment, "holdout", pid, 0.0))
    return rows


def record_recommendations(spark: Any, catalog: str, schema: str, run_id: str,
                           question: str, result: BriefingResult) -> int:
    """Append this run's outreach batches to the ledger table. Returns rows written."""
    rows = ledger_rows(run_id, question, result.tool_outputs, datetime.now(timezone.utc))
    if not rows:
        return 0
    df = spark.createDataFrame(rows, schema=LEDGER_DDL)
    df.write.format("delta").mode("append").saveAsTable(f"{catalog}.{schema}.{LEDGER_TABLE}")
    return len(rows)
