# Revenue Briefing Agent — ACM x Xorbix × UIowa Hackathon 2026

**One question. Four tools. Ranked actions with $ impact.**

Agentic AI on **Databricks Free Edition** for a chiropractic clinic — covers **leads**, **retention**, and **pricing** in one daily briefing.

**Repo:** https://github.com/ptouhy/acm-xorbix-hackathon

---

## Quick demo (Databricks)

1. **Repos → Pull** latest
2. Open `notebooks/03_run_briefing.py`
3. Run all cells (pip → restart → agent runs)

Default question: *"What should we focus on today to maximize revenue?"*

---

## Progress checklist

- [x] Step 1 — `notebooks/generate_synthetic_data.py` → 8 UC tables
- [x] Step 2 — `notebooks/02_explore_data.py` → understand the data
- [x] Step 3–5 — **Revenue Briefing Agent** (this build)

---

## Project layout

```
config/settings.yaml       # Catalog, thresholds, $ assumptions (no secrets)
agent/
  tools.py                 # 4 Spark SQL tools (leads / retention / pricing)
  briefing.py              # Orchestrator — runs tools, ranks, formats
notebooks/
  generate_synthetic_data.py
  02_explore_data.py
  03_run_briefing.py       # ← main demo
databricks.yml             # DAB — deploy job + MLflow experiment
docs/HOW_IT_WORKS.md       # Architecture explained
docs/PITCH.md              # 2-minute pitch script
tests/                     # pytest for ranking logic
```

---

## Deploy (DAB)

```bash
databricks auth login --host https://YOUR-WORKSPACE.cloud.databricks.com
databricks bundle validate
databricks bundle deploy -t dev
databricks bundle run revenue_briefing -t dev
```

Edit `catalog` / `schema` in `config/settings.yaml` or `databricks.yml` variables.

---

## Local tests

```bash
pip install pyyaml pytest
pytest
```

---

## Team

Patrick + Tommy
