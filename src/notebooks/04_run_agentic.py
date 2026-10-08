# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# MAGIC %md
# MAGIC # Step 6 — Agentic Revenue Briefing Agent
# MAGIC
# MAGIC Unlike notebook 03 (fixed pipeline), here an **LLM decides which tools to call**.
# MAGIC Ask a narrow question and it runs fewer tools; ask a broad one and it runs them all.
# MAGIC The trace below shows every decision. If the LLM endpoint is down, it falls back to notebook 03's logic.

# COMMAND ----------

# MAGIC %pip install pyyaml "databricks-sdk[openai]" -q

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

import sys

nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
repo_root = "/Workspace" + nb_path.rsplit("/notebooks/", 1)[0]
sys.path.insert(0, repo_root)

from agent.agentic import AgenticBriefingAgent
from agent.llm import DatabricksLLM

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "chiro_hackathon")
dbutils.widgets.text("question", "What should we focus on today to maximize revenue?")
dbutils.widgets.text("experiment_path", "")  # blank = /Users/<you>/revenue_briefing_agent
dbutils.widgets.text("llm_endpoint", "")  # blank = use agent.llm_endpoint from config/settings.yaml

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
question = dbutils.widgets.get("question")
llm_endpoint = dbutils.widgets.get("llm_endpoint")
experiment_path = dbutils.widgets.get("experiment_path")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Watch the agent work (streamed steps)

# COMMAND ----------

import time

start = time.time()
llm = DatabricksLLM(llm_endpoint) if llm_endpoint else None
agent = AgenticBriefingAgent(spark, catalog=catalog, schema=schema, llm=llm)  # noqa: F821
result = None

for event in agent.run_stream(question):
    if event.type == "tool_call":
        args = event.data.get("args")
        print(f"→ calling {event.data['tool']}" + (f" {args}" if args else ""))
    elif event.type == "plan":
        print("📋 Plan: " + " → ".join(event.data["steps"]))
    elif event.type == "tool_result":
        out = event.data["output"]
        if event.data["tool"] == "record_plan":
            pass
        elif "error" in out:
            print(f"  ✗ {event.data['tool']}: {out['error']}")
        elif "ranked_actions" in out:
            print(f"  ✓ ranked {len(out['ranked_actions'])} actions, total ${out['total_estimated_impact_usd']:,.0f}")
        else:
            print(f"  ✓ {event.data['tool']}: ${out.get('estimated_impact_usd', 0):,.0f}")
            if out.get("kind") in ("diagnostic", "action"):
                print(f"    ↳ {out['recommendation']}")
    elif event.type == "fallback":
        print(f"⚠ Fell back to the deterministic briefing: {event.data['reason']}")
        result = event.data["result"]
    elif event.type == "final":
        result = event.data["result"]

print()
print(result.briefing_text)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Measure — log the run (MLflow) and record who was recommended (ledger + holdout)

# COMMAND ----------

from agent.tracking import log_run, record_recommendations

if not experiment_path:
    user = dbutils.notebook.entry_point.getDbutils().notebook().getContext().userName().get()  # noqa: F821
    experiment_path = f"/Users/{user}/revenue_briefing_agent"
run_id = log_run(result, experiment_path, catalog, schema, time.time() - start)
try:
    n = record_recommendations(spark, catalog, schema, run_id, question, result)  # noqa: F821
    print(f"MLflow run {run_id}; recorded {n} contacted/holdout rows in {catalog}.{schema}.agent_recommendations")
except Exception as exc:
    print(f"Ledger write skipped (non-fatal): {exc}")
