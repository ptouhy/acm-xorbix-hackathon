# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Run Clinic Growth Agent
# MAGIC Agentic demo: selects tools by focus area, returns actionable recommendations.
# MAGIC Set `use_model=true` to synthesize via Foundation Model (Free Edition).

# COMMAND ----------

import sys
from pathlib import Path

bundle_root = Path.cwd()
if (bundle_root / "src").exists():
    sys.path.insert(0, str(bundle_root / "src"))

from acm_hackathon.agents import ClinicGrowthAgent
from acm_hackathon.data.sample_data import all_sample_tables

# COMMAND ----------

dbutils.widgets.text("question", "Which leads should we prioritize today?")
dbutils.widgets.dropdown("use_model", "false", ["false", "true"])

question = dbutils.widgets.get("question")
use_model = dbutils.widgets.get("use_model").lower() == "true"

# COMMAND ----------

# Optional: load from Unity Catalog instead of sample data
# catalog, schema = "main", "clinic_hackathon"
# tables = {t: spark.table(f"{catalog}.{schema}.{t}").toPandas() for t in [...]}

agent = ClinicGrowthAgent(tables=all_sample_tables())
response = agent.ask(question, use_model=use_model)

print(f"Mode: {response.mode}")
print(response.answer)

# COMMAND ----------

# MLflow trace (Free Edition)
import mlflow

mlflow.set_experiment("/Shared/acm-xorbix-hackathon/clinic_growth_agent")
with mlflow.start_run(run_name="agent_query"):
    mlflow.log_param("question", question)
    mlflow.log_param("mode", response.mode)
    mlflow.log_param("tools", [c["tool"] for c in response.tool_calls])
    mlflow.log_text(response.answer, "answer.txt")
