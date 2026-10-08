# Databricks notebook source
# MAGIC %md
# MAGIC # Eval — does the agent pick the right tools?
# MAGIC
# MAGIC Runs each case in `agent/evals.py` several times against the real LLM and scores which tools were called
# MAGIC (and with which arguments). Use it to compare models (`llm_endpoint` widget) and to put a measured
# MAGIC reliability number in the pitch. Does **not** write to the recommendation ledger.

# COMMAND ----------

# MAGIC %pip install pyyaml "databricks-sdk[openai]" -q

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

import sys

nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
sys.path.insert(0, "/Workspace" + nb_path.rsplit("/notebooks/", 1)[0])

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "chiro_hackathon")
dbutils.widgets.text("llm_endpoint", "")  # blank = endpoint from config/settings.yaml
dbutils.widgets.text("runs", "5")
dbutils.widgets.text("experiment_path", "")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
llm_endpoint = dbutils.widgets.get("llm_endpoint")
runs = int(dbutils.widgets.get("runs"))
experiment_path = dbutils.widgets.get("experiment_path")

# COMMAND ----------

from agent.agentic import AgenticBriefingAgent
from agent.evals import CASES, overall_pass_rate, run_eval
from agent.llm import DatabricksLLM
from agent.settings import load_settings

endpoint = llm_endpoint or load_settings()["agent"]["llm_endpoint"]
print(f"Model: {endpoint} | {len(CASES)} cases x {runs} runs")


def make_agent():
    agent = AgenticBriefingAgent(spark, catalog=catalog, schema=schema, llm=DatabricksLLM(endpoint))  # noqa: F821
    agent.settings["agent"]["stage_outreach"] = False  # evals must not fill the real outreach queue
    return agent


def progress(case_id, i, failures):
    print(f"  {case_id} #{i + 1}: " + ("PASS" if not failures else "FAIL " + "; ".join(failures)))


results = run_eval(make_agent, CASES, runs, on_run=progress)
overall = overall_pass_rate(results)

# COMMAND ----------

try:
    import mlflow

    if not experiment_path:
        user = dbutils.notebook.entry_point.getDbutils().notebook().getContext().userName().get()  # noqa: F821
        experiment_path = f"/Users/{user}/revenue_briefing_agent"
    mlflow.set_experiment(experiment_path)
    with mlflow.start_run(run_name="tool_selection_eval"):
        mlflow.log_params({"llm_endpoint": endpoint, "runs_per_case": runs, "cases": len(CASES)})
        mlflow.log_metric("overall_pass_rate", overall)
        for r in results:
            mlflow.log_metric(f"pass_rate_{r['case']}", r["pass_rate"])
        mlflow.log_dict(results, "eval_results.json")
    print("Logged to MLflow.")
except Exception as exc:
    print(f"MLflow logging skipped (non-fatal): {exc}")

# COMMAND ----------

print(f"\n=== Tool-selection pass rate ({endpoint}) ===")
for r in results:
    print(f"{r['case']:>17}: {r['passes']}/{r['runs']}  {r['top_failures']}")
print(f"\nOVERALL: {overall:.0%}")

import pandas as pd
display(pd.DataFrame(results))  # noqa: F821
