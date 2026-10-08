# Databricks notebook source
# MAGIC %md
# MAGIC # Step 7 — Measure: did the recommended outreach work?
# MAGIC
# MAGIC Every time the agent drafts an outreach list, it records the contacted people **and a same-size holdout**
# MAGIC (next in line, not contacted) in `agent_recommendations`. This notebook compares the two groups:
# MAGIC leads → converted, patients → still Active. Judged only after `min_followup_days`; before that it reports the baseline.

# COMMAND ----------

import sys

nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
sys.path.insert(0, "/Workspace" + nb_path.rsplit("/notebooks/", 1)[0])

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "chiro_hackathon")
catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")

# COMMAND ----------

from agent.measure import measure_outcomes
from agent.tracking import LEDGER_TABLE

if not spark.catalog.tableExists(f"{catalog}.{schema}.{LEDGER_TABLE}"):  # noqa: F821
    print("No recommendations recorded yet. Run notebook 04 first.")
else:
    results = measure_outcomes(spark, catalog, schema)  # noqa: F821
    for r in results:
        print(f"[{r['segment']}] run {r['run_id'][:8]}  ({r['days_since']}d ago)")
        print(f"   contacted {r['contacted_n']}: {r['contacted_rate_pct']}%   holdout {r['holdout_n']}: {r['holdout_rate_pct']}%   lift: {r['lift_pts']}")
        print(f"   expected impact ${r['expected_impact_usd']:,.0f}  ->  {r['verdict']}")
    if results:
        import pandas as pd
        display(pd.DataFrame(results))  # noqa: F821
