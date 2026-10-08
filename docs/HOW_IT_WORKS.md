# How the Revenue Briefing Agent works

## The idea (one sentence)

Staff ask **one question**; the agent runs **four analysis tools** on Unity Catalog data and returns **ranked actions with dollar impact** across leads, retention, and pricing.

---

## Architecture

```
Question
   ↓
AgenticBriefingAgent (src/agent/agentic.py)  ⇄  LLM (Model Serving, tool calling)
   ↓ chooses tools, with arguments
┌─ ANALYSIS (size $) ──────────────────────────────┐
│ find_stale_leads · find_top_lead_sources         │
│ find_churn_risk_patients · find_revenue_leaks    │
├─ DIAGNOSTIC (why) ───────────────────────────────┤
│ diagnose_no_shows · diagnose_lead_response       │
├─ ACTION (do) ────────────────────────────────────┤
│ draft_outreach(segment, limit)                   │
└──────────────────────────────────────────────────┘
   ↓
rank_actions() — sorts ANALYSIS results by estimated_impact_usd
   ↓
Briefing (+ "Why" findings + call list, appended in code)
   ↓
MLflow log · agent_recommendations ledger (contacted + holdout) · 05_measure_outcomes
```

Guards (all tested): `rank_actions` refuses to run before any analysis tool; totals are computed in
code; diagnostics refuse to report differences that are within random variation; off-topic questions
get a short reply with no tools; any LLM failure falls back to the fixed pipeline.

---

## File map

| File | Purpose |
|------|---------|
| `config/settings.yaml` | Catalog, schema, $ assumptions, thresholds, LLM endpoint |
| `src/agent/tools.py` | Spark SQL tools: analysis, diagnostic, draft_outreach |
| `src/agent/registry.py` | Tool descriptions + argument schemas shown to the LLM, and dispatch |
| `src/agent/llm.py` | Model Serving client |
| `src/agent/agentic.py` | The LLM tool-calling loop, guards, fallback |
| `src/agent/briefing.py` | Ranking/formatting + the original fixed-pipeline agent (the fallback) |
| `src/agent/tracking.py` | MLflow logging + recommendation ledger |
| `src/agent/measure.py` | Contacted-vs-holdout outcome comparison |
| `src/notebooks/04_run_agentic.py` | Agent demo + logging |
| `src/notebooks/05_measure_outcomes.py` | Measure step |
| `src/agent/evals.py`, `src/notebooks/06_eval_tool_selection.py` | Tool-selection eval: 10 questions × N runs, scored on tools and arguments (job `evaluate_agent`) |
| `sample_data/generate_synthetic_data.py` | Synthetic data generator (run by the `setup_data` job) |
| `databricks.yml`, `resources/` | DAB: variables, 2 jobs, MLflow experiment |

---

## Tool details

**Analysis** (each returns `estimated_impact_usd`)
- `find_stale_leads`: open leads in an actionable window. Recent (3-30 days): count × eval revenue × conversion rate. Dormant (31-180 days): count × eval revenue × a lower win-back rate. Older leads are excluded as too cold.
- `find_churn_risk_patients`: Active patients whose last visit was 60-180 days ago (they stopped coming), defined from visit history because the provided churn-risk score had no relationship to actual churn in this data; impact = count × visits × visit revenue × re-engagement rate.
- `find_revenue_leaks`: prices the last 12 months of no-shows (count × measured revenue per visit × a recovery-rate assumption). Package Plan economics and marketing cost per conversion are reported but not priced, because the data shows no package revenue premium and marketing returns may not scale.
- `find_top_lead_sources`: win rate by source (Converted / (Converted + Lost)), with a significance test. If no source stands out, it says so and prices nothing.

**Diagnostic**
- `diagnose_no_shows`: no-show rate by appointment type, booking channel, booking lead time and location versus the clinic baseline; only segments beating it by `min_lift_pts` count.
- `diagnose_lead_response`: win rate by speed of first response, with a two-proportion z-test (`min_z_score`).

**Action**
- `draft_outreach`: top N people for `stale_leads` or `churn_risk_patients`, a message template, and an equal-size holdout (the next people in priority order, not contacted). It also **stages the list in `outreach_queue` as `pending_approval`** (people already pending are skipped); staff approve it in the web UI.

---

## Run locally (tests only)

```bash
pip install pyyaml pytest
pytest
```

## Run on Databricks

1. Repos → Pull latest
2. Open `src/notebooks/03_run_briefing.py`
3. Run all cells

## Deploy via DAB

```bash
databricks bundle deploy -t dev
databricks bundle run revenue_briefing -t dev
```

---

See [PITCH.md](PITCH.md) for the 2-minute pitch.
