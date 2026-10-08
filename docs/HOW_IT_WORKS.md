# How the Revenue Briefing Agent works

## The idea (one sentence)

Staff ask **one question**; the agent runs **four analysis tools** on Unity Catalog data and returns **ranked actions with dollar impact** across leads, retention, and pricing.

---

## Architecture

```
Question
   ↓
AgenticBriefingAgent (agent/agentic.py)  ⇄  LLM (Model Serving, tool calling)
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
| `agent/tools.py` | Spark SQL tools: analysis, diagnostic, draft_outreach |
| `agent/registry.py` | Tool descriptions + argument schemas shown to the LLM, and dispatch |
| `agent/llm.py` | Model Serving client |
| `agent/agentic.py` | The LLM tool-calling loop, guards, fallback |
| `agent/briefing.py` | Ranking/formatting + the original fixed-pipeline agent (the fallback) |
| `agent/tracking.py` | MLflow logging + recommendation ledger |
| `agent/measure.py` | Contacted-vs-holdout outcome comparison |
| `notebooks/04_run_agentic.py` | Agent demo + logging |
| `notebooks/05_measure_outcomes.py` | Measure step |
| `databricks.yml`, `resources/` | DAB: variables, job (2 tasks), MLflow experiment |

---

## Tool details

**Analysis** (each returns `estimated_impact_usd`)
- `find_stale_leads`: open leads older than the stale threshold; impact = count × eval revenue × conversion rate.
- `find_churn_risk_patients`: Active patients above the churn threshold; impact = count × visits × visit revenue × re-engagement rate.
- `find_revenue_leaks`: no-show rate, Package Plan share, cheapest marketing channel.
- `find_top_lead_sources`: best-converting sources among open leads.

**Diagnostic**
- `diagnose_no_shows`: no-show rate by appointment type, booking channel, booking lead time and location versus the clinic baseline; only segments beating it by `min_lift_pts` count.
- `diagnose_lead_response`: win rate by speed of first response, with a two-proportion z-test (`min_z_score`).

**Action**
- `draft_outreach`: top N people for `stale_leads` or `churn_risk_patients`, a message template, and an equal-size holdout (the next people in priority order, not contacted).

---

## Run locally (tests only)

```bash
pip install pyyaml pytest
pytest
```

## Run on Databricks

1. Repos → Pull latest
2. Open `notebooks/03_run_briefing.py`
3. Run all cells

## Deploy via DAB

```bash
databricks bundle deploy -t dev
databricks bundle run revenue_briefing -t dev
```

---

See [PITCH.md](PITCH.md) for the 2-minute pitch.
