# Databricks notebook source
# MAGIC %md
# MAGIC # 00 — Setup Unity Catalog (Free Edition)
# MAGIC Creates schema for clinic hackathon tables.

# COMMAND ----------

dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "clinic_hackathon")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
print(f"Ready: {catalog}.{schema}")
