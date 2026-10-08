# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# MAGIC %md
# MAGIC # Step 3–5 — Revenue Briefing Agent (full demo)
# MAGIC
# MAGIC **One question → agent runs 4 tools → ranked actions with $ impact.**
# MAGIC
# MAGIC Covers all hackathon focus areas:
# MAGIC - **Leads** — stale pipeline + top sources
# MAGIC - **Retention** — high churn-risk patients
# MAGIC - **Pricing** — no-shows, package mix, marketing ROI

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup (run once per session)
# MAGIC 1. `%pip install pyyaml` — reads `config/settings.yaml`
# MAGIC 2. `%restart_python` — required after pip
# MAGIC 3. Add repo root to path so `import agent` works

# COMMAND ----------

# MAGIC %pip install pyyaml -q

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

import sys

nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
repo_root = "/Workspace" + nb_path.rsplit("/notebooks/", 1)[0]
sys.path.insert(0, repo_root)

print(f"Repo root: {repo_root}")

from agent.briefing import RevenueBriefingAgent

# COMMAND ----------

# MAGIC %md
# MAGIC ## Widgets — change question or catalog if needed

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "chiro_hackathon")
dbutils.widgets.text("question", "What should we focus on today to maximize revenue?")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
question = dbutils.widgets.get("question")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run the agent
# MAGIC The orchestrator calls 4 tools, ranks by $ impact, returns a briefing.

# COMMAND ----------

agent = RevenueBriefingAgent(spark, catalog=catalog, schema=schema)  # noqa: F821
result = agent.run(question)

print(result.briefing_text)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Structured output (for judges / debugging)

# COMMAND ----------

import pandas as pd

summary = pd.DataFrame([
    {
        "rank": a["rank"],
        "focus": a["focus"],
        "impact_usd": a["estimated_impact_usd"],
        "recommendation": a["recommendation"],
    }
    for a in result.actions
])
display(summary)  # noqa: F821

# COMMAND ----------

# MAGIC %md
# MAGIC ## MLflow — log the briefing (Databricks-native observability)

# COMMAND ----------

import mlflow

# Free Edition: /Shared/... often doesn't exist — use your user folder instead
user = dbutils.notebook.entry_point.getDbutils().notebook().getContext().userName().get()
experiment_path = f"/Users/{user}/acm-xorbix-hackathon/revenue_briefing_agent"

try:
    mlflow.set_experiment(experiment_path)
    with mlflow.start_run(run_name="daily_briefing"):
        mlflow.log_param("question", question)
        mlflow.log_param("catalog", catalog)
        mlflow.log_param("schema", schema)
        mlflow.log_metric("total_estimated_impact_usd", result.total_estimated_impact_usd)
        mlflow.log_param("tools_used", [t["tool"] for t in result.tool_outputs])
        mlflow.log_text(result.briefing_text, "briefing.md")
        mlflow.log_dict({"actions": result.actions}, "actions.json")
    print(f"Logged to MLflow: {experiment_path}")
except Exception as exc:
    print(f"MLflow logging skipped (non-fatal): {exc}")
    print("Your briefing above is still valid — this cell is optional for the demo.")
print("Logged to MLflow experiment: /Shared/acm-xorbix-hackathon/revenue_briefing_agent")
