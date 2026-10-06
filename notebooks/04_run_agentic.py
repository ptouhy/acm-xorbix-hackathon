# Databricks notebook source
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

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "chiro_hackathon")
dbutils.widgets.text("question", "What should we focus on today to maximize revenue?")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
question = dbutils.widgets.get("question")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Watch the agent work (streamed steps)

# COMMAND ----------

agent = AgenticBriefingAgent(spark, catalog=catalog, schema=schema)  # noqa: F821
result = None

for event in agent.run_stream(question):
    if event.type == "tool_call":
        print(f"→ calling {event.data['tool']}")
    elif event.type == "tool_result":
        out = event.data["output"]
        print(f"  ✓ {event.data['tool']}: ${out.get('estimated_impact_usd', 0):,.0f}" if "error" not in out
              else f"  ✗ {event.data['tool']}: {out['error']}")
    elif event.type == "fallback":
        print(f"⚠ LLM unavailable, using deterministic briefing ({event.data['reason']})")
        result = event.data["result"]
    elif event.type == "final":
        result = event.data["result"]

print()
print(result.briefing_text)
