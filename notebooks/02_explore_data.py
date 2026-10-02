# Databricks notebook source
# MAGIC %md
# MAGIC # Step 2 — Explore the Clinic Data
# MAGIC
# MAGIC **Goal:** Understand what we have before building an agent.
# MAGIC
# MAGIC All tables: `workspace.chiro_hackathon.*`
# MAGIC
# MAGIC Run each cell. Read the results. Ask: *what business question could an AI help answer here?*

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. What tables do we have?

# COMMAND ----------

spark.sql("SHOW TABLES IN workspace.chiro_hackathon").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Patients — who's active vs lapsed?
# MAGIC
# MAGIC `churn_risk_score` = 0 to 1 (higher = more likely to leave)

# COMMAND ----------

spark.sql("""
SELECT status, COUNT(*) AS patient_count, ROUND(AVG(churn_risk_score), 3) AS avg_churn_risk
FROM workspace.chiro_hackathon.patients
GROUP BY status
ORDER BY patient_count DESC
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Leads — funnel: how many convert?

# COMMAND ----------

spark.sql("""
SELECT status, COUNT(*) AS lead_count,
       ROUND(100.0 * SUM(CASE WHEN converted_flag THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_converted
FROM workspace.chiro_hackathon.leads
GROUP BY status
ORDER BY lead_count DESC
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Leads — which sources work best?

# COMMAND ----------

spark.sql("""
SELECT source,
       COUNT(*) AS leads,
       SUM(CASE WHEN converted_flag THEN 1 ELSE 0 END) AS conversions,
       ROUND(100.0 * SUM(CASE WHEN converted_flag THEN 1 ELSE 0 END) / COUNT(*), 1) AS conversion_rate_pct
FROM workspace.chiro_hackathon.leads
GROUP BY source
ORDER BY conversion_rate_pct DESC
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Visits — where does revenue come from?

# COMMAND ----------

spark.sql("""
SELECT service_type,
       COUNT(*) AS visits,
       ROUND(SUM(revenue), 2) AS total_revenue,
       ROUND(AVG(revenue), 2) AS avg_revenue_per_visit
FROM workspace.chiro_hackathon.visits
GROUP BY service_type
ORDER BY total_revenue DESC
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Appointments — no-show problem?

# COMMAND ----------

spark.sql("""
SELECT status, COUNT(*) AS appointment_count,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_of_all
FROM workspace.chiro_hackathon.appointments
GROUP BY status
ORDER BY appointment_count DESC
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Marketing — cost per conversion by channel

# COMMAND ----------

spark.sql("""
SELECT channel,
       COUNT(*) AS campaigns,
       ROUND(SUM(budget), 2) AS total_spend,
       SUM(conversions) AS total_conversions,
       ROUND(SUM(budget) / NULLIF(SUM(conversions), 0), 2) AS cost_per_conversion
FROM workspace.chiro_hackathon.marketing_campaigns
GROUP BY channel
ORDER BY cost_per_conversion ASC
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. The money question — high-risk patients
# MAGIC
# MAGIC Active patients with high churn risk = retention opportunity.

# COMMAND ----------

spark.sql("""
SELECT COUNT(*) AS high_risk_active_patients
FROM workspace.chiro_hackathon.patients
WHERE status = 'Active' AND churn_risk_score >= 0.75
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ### Step 2 checkpoint
# MAGIC
# MAGIC You should now see patterns like:
# MAGIC - Which lead sources convert best
# MAGIC - Which services drive revenue
# MAGIC - How big the no-show / churn problem is
# MAGIC
# MAGIC **Step 3** = pick ONE business question and write one Python function to answer it.
# MAGIC
# MAGIC Tell your teammate: *"Step 2 done — I think our agent should focus on ___"*
