# How the Revenue Briefing Agent works

## The idea (one sentence)

Staff ask **one question**; the agent runs **four analysis tools** on Unity Catalog data and returns **ranked actions with dollar impact** across leads, retention, and pricing.

---

## Architecture

```
Question
   ↓
RevenueBriefingAgent (orchestrator)
   ↓
┌──────────────┬─────────────────┬──────────────────┬────────────────────┐
│ stale leads  │ churn risk      │ revenue leaks    │ top lead sources   │
│ (leads)      │ (retention)     │ (pricing)        │ (leads)            │
└──────────────┴─────────────────┴──────────────────┴────────────────────┘
   ↓
rank_actions() — sort by estimated_impact_usd
   ↓
Markdown briefing + MLflow log
```

---

## File map

| File | Purpose |
|------|---------|
| `config/settings.yaml` | Catalog, schema, $ assumptions, thresholds — **not in code** |
| `agent/tools.py` | 4 Spark SQL tools (one per business question) |
| `agent/briefing.py` | Orchestrator: run tools → rank → format |
| `agent/settings.py` | Loads YAML config |
| `notebooks/03_run_briefing.py` | Demo notebook (what judges see) |
| `databricks.yml` | DAB — deploy job + MLflow experiment |

---

## Tool details

### 1. `find_stale_leads` (Leads)
- **SQL:** open leads older than 3 days
- **Impact:** stale_count × $150 eval × 20% conversion

### 2. `find_churn_risk_patients` (Retention)
- **SQL:** Active patients with churn_risk_score ≥ 0.75
- **Impact:** count × 4 visits × $75 × 25% re-engage rate

### 3. `find_revenue_leaks` (Pricing)
- **SQL:** no-show rate, Package Plan %, best marketing channel
- **Impact:** recoverable no-show revenue + package upsell opportunity

### 4. `find_top_lead_sources` (Leads)
- **SQL:** best converting sources among open leads
- **Impact:** prioritization for today's calls

### 5. `rank_actions` (Agent brain)
- Pure Python — sorts all tool outputs by `estimated_impact_usd`
- Returns top 5 for the briefing

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

## 2-minute pitch outline

1. **Problem (30s):** Clinics lose revenue across leads, churn, and pricing — no single view of what to do *today*.
2. **Solution (45s):** Revenue Briefing Agent on Databricks — one question, four tools, ranked $ impact.
3. **How built (45s):** Synthetic UC data, Spark SQL tools, Python orchestrator, MLflow, DAB deploy.
