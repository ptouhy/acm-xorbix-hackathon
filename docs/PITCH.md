# 2-minute elevator pitch — Revenue Briefing Agent

## Problem (30 seconds)

Boutique chiropractic clinics scaling toward $250M ARR lose money in three places every day: **leads go cold**, **patients churn**, and **pricing and marketing don't line up with revenue**. Managers don't need another dashboard — they need to know **what to do this morning**.

## Solution (45 seconds)

We built the **Revenue Briefing Agent** on Databricks Free Edition. You ask one question — *"What should we focus on today to maximize revenue?"* — and the agent runs **four tools** over 60,000 patients, 45,000 leads, and 259,000 visits. It returns **five ranked actions with estimated dollar impact**, covering leads, retention, and pricing in one workflow.

## How we built it (45 seconds)

- **Data:** Official synthetic dataset in Unity Catalog (`workspace.chiro_hackathon`)
- **Tools:** Spark SQL functions — each answers one business question
- **Agent:** Python orchestrator ranks actions by impact
- **Observability:** MLflow logs every briefing
- **Deploy:** Databricks Asset Bundle — clone repo, set catalog/schema, run

## Demo line

> "In our synthetic clinic, the agent found **$X total estimated opportunity** — starting with **Y high-churn patients** and **Z stale leads**."

*(Replace X/Y/Z with numbers from your live run.)*
