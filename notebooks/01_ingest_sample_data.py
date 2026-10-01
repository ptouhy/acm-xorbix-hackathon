# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Ingest Sample Clinic Data
# MAGIC Loads synthetic CSV-equivalent data into Unity Catalog tables.

# COMMAND ----------

import sys
from pathlib import Path

# Bundle sync places src at workspace path — adjust for local vs bundle context
bundle_root = Path.cwd()
if (bundle_root / "src").exists():
    sys.path.insert(0, str(bundle_root / "src"))
elif (bundle_root.parent / "src").exists():
    sys.path.insert(0, str(bundle_root.parent / "src"))

from acm_hackathon.data.sample_data import all_sample_tables

# COMMAND ----------

dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "clinic_hackathon")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")

# COMMAND ----------

for name, pdf in all_sample_tables().items():
    sdf = spark.createDataFrame(pdf)  # noqa: F821 — Databricks runtime
    fq = f"{catalog}.{schema}.{name}"
    sdf.write.mode("overwrite").saveAsTable(fq)
    print(f"Wrote {fq} ({sdf.count()} rows)")
