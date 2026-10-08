# Live demo guide

## Before you present (5 minutes)

1. **Log in:** `databricks auth login --host https://<your-workspace>.cloud.databricks.com` (once; opens a browser).
2. **Start the app** (from the repo root):
   ```bash
   PYTHONPATH=src .venv/bin/uvicorn app.server:app --port 8000
   ```
   Open http://localhost:8000.
3. **Warm up the SQL warehouse** (it sleeps when idle, and the first query takes ~40s): click a suggested question once and let it finish. Do this before anyone is watching.
4. **Clean the queue** so the demo starts fresh (optional): in a Databricks SQL editor run
   `DELETE FROM workspace.chiro_hackathon.outreach_queue;`
   Otherwise the agent skips people who are already pending and says "0 new, 10 already pending".
5. Have a **backup**: a screenshot or short screen recording of a good run, in case the Wi-Fi or the model endpoint fails.

## The flow (about 90 seconds on screen)

| Step | Do this | Say this |
|---|---|---|
| 1 | Click **"What should we focus on today to maximize revenue?"** | "A manager asks one question. The agent doesn't run a fixed report. It plans first, then picks its own tools." |
| 2 | Point at **Agent plan** and the **Agent activity** log as it fills | "Observe: it sizes leads, lapsing patients and no-show losses straight from Unity Catalog. Each step is a real SQL query on Databricks." |
| 3 | Point at the **ranked cards** and the headline number | "Decide: it ranks by dollar impact: about **$835K**, led by retention at $555K. The total is computed in code, not by the LLM, so it can't invent numbers." |
| 4 | Scroll to **Act now** | "Act: it drafts today's call list and message for the 10 most loyal lapsing patients, and stages it in an outreach queue." |
| 5 | Click **Approve batch** | "A human signs off. The agent acts, staff stay in control." |
| 6 | Click the question **"Why are we losing appointments to no-shows?"** | "Reason: it diagnoses. Here it says no-shows are spread evenly, so segment targeting won't help. It won't invent a pattern." |
| 7 | Open the **Measure** tab | "Measure: every list is saved with a same-size holdout that isn't contacted. After outreach we compare the two groups and see the lift. Right now it's the baseline." |
| 8 | (Optional) ask **"What is the weather today?"** | "It refuses off-topic questions and calls no tools." |

## Numbers you can quote (they drift slightly day to day)

- **Total opportunity ≈ $835K:** retention $555K (5,783 patients who stopped visiting 60 to 180 days ago), pricing $254K a year (8,814 no-shows in the last 12 months), leads $26K (570 recently quiet leads plus 2,739 dormant).
- That's about **14% of the data's $6.1M** trailing-12-month revenue.
- **Tool-selection eval:** 98% (49 of 50 runs) on the previous version of the agent. Rerun `databricks bundle run evaluate_agent -t dev` if you want a current figure before quoting it.

## If something goes wrong

| Problem | Fix |
|---|---|
| First run is slow | The warehouse is waking up. Keep talking about the business problem. |
| The page says "Fell back to the fixed-pipeline briefing" | The LLM endpoint hiccuped. The numbers are still right. Say "this is our safety net", then re-run. |
| Page won't load | Restart the app and use the backup recording. |
| A judge asks "are the numbers real?" | Estimates from the synthetic data plus assumptions in `config/settings.yaml` (visit value is measured; conversion and recovery rates are assumptions). |

## Questions you may get

- **"Why are the lead numbers small?"** We only count actionable leads (3 to 30 days quiet at full odds, 31 to 180 as win-back). An earlier version counted 26,900 "stale" leads, mostly over a year old, and we cut them.
- **"Why not use the churn-risk score?"** We tested it: it averaged 0.549 for Active and 0.547 for Churned patients, so it predicted nothing. We defined at-risk by behavior instead (stopped visiting).
- **"Is it deployed through the bundle?"** Yes. One `databricks bundle deploy` creates the jobs (data setup, agent, measure, eval) and the MLflow experiment, with no workspace values in the code. The web UI is a presentation layer that runs the same agent code locally.
- **"Where is the human in the loop?"** The agent stages outreach as `pending_approval`; staff approve it.
