# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Run Clinic Growth Agent
# MAGIC
# MAGIC **Run cells top-to-bottom.** Cell 1 installs the package, Cell 2 restarts Python, then imports work.

# COMMAND ----------

# MAGIC %pip install "git+https://github.com/ptouhy/acm-xorbix-hackathon.git" pyyaml python-dotenv -q

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

from acm_hackathon.agents import ClinicGrowthAgent
from acm_hackathon.data.loader import load_agent_tables_spark, validate_tables_exist

print("acm_hackathon imported successfully")

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "chiro_hackathon")
dbutils.widgets.text("question", "Which patients are at risk of dropping off and what should we do?")
dbutils.widgets.dropdown("use_model", "false", ["false", "true"])

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
question = dbutils.widgets.get("question")
use_model = dbutils.widgets.get("use_model").lower() == "true"

# COMMAND ----------

missing = validate_tables_exist(spark, catalog, schema)  # noqa: F821
if missing:
    raise RuntimeError(
        f"Missing tables: {missing}. Run notebooks/generate_synthetic_data.py first."
    )

print(f"Loading agent tables from {catalog}.{schema} ...")
tables = load_agent_tables_spark(spark, catalog, schema)  # noqa: F821
for name, df in tables.items():
    print(f"  {name}: {len(df):,} rows")

# COMMAND ----------

agent = ClinicGrowthAgent(tables=tables)
response = agent.ask(question, use_model=use_model)

print(f"\nMode: {response.mode}")
print(f"Tools used: {[c['tool'] for c in response.tool_calls]}")
print("\n" + "=" * 60)
print(response.answer)

# COMMAND ----------

import mlflow

mlflow.set_experiment("/Shared/acm-xorbix-hackathon/clinic_growth_agent")
with mlflow.start_run(run_name="agent_query"):
    mlflow.log_param("question", question)
    mlflow.log_param("catalog", catalog)
    mlflow.log_param("schema", schema)
    mlflow.log_param("mode", response.mode)
    mlflow.log_param("tools", [c["tool"] for c in response.tool_calls])
    mlflow.log_text(response.answer, "answer.txt")
