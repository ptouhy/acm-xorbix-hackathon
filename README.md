# Revenue Briefing Agent — ACM x Xorbix × UIowa Hackathon 2026

**An agentic AI that tells a chiropractic clinic what to do today to grow revenue.**

An LLM agent on **Databricks Free Edition** investigates clinic data across **leads**, **retention**, and **pricing**. It decides which analysis tools to call, then returns ranked actions with estimated dollar impact.

**Repo:** https://github.com/ptouhy/acm-xorbix-hackathon

---

## How it works

```
question → LLM (Databricks Model Serving) ⇄ tools (Spark SQL on Unity Catalog)
                  ↓
   ranked actions + $ impact + briefing   (falls back to a fixed pipeline if the LLM is unavailable)
```

- The LLM **chooses** which tools to call; broad questions use all of them, narrow ones use fewer.
- Tools: `find_stale_leads`, `find_top_lead_sources`, `find_churn_risk_patients`, `find_revenue_leaks`.
- All dollar assumptions live in `config/settings.yaml`, not in code.
- Details: [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) · Pitch: [docs/PITCH.md](docs/PITCH.md)

---

## Prerequisites

- A Databricks workspace (Free Edition works) with serverless compute
- A Model Serving endpoint that supports tool calling (default: `databricks-meta-llama-3-3-70b-instruct`; check **Serving** in your workspace)
- [Databricks CLI](https://docs.databricks.com/dev-tools/cli/install.html) v0.250+ (`brew install databricks`)
- Python 3.10+ for local tests

No secrets or workspace URLs are stored in this repo. Authentication comes from your CLI profile.

---

## Setup

```bash
git clone https://github.com/ptouhy/acm-xorbix-hackathon.git
cd acm-xorbix-hackathon
databricks auth login --host https://<your-workspace>.cloud.databricks.com
```

**Create the synthetic data (once per workspace):** in Databricks, run `notebooks/generate_synthetic_data.py`. It creates 8 tables in `<catalog>.chiro_hackathon`.
(To run it from a Git folder: **Workspace → Create → Git folder** → paste the repo URL.)

---

## Validate

```bash
databricks bundle validate -t dev
```

Local unit tests (no Databricks needed — they use a fake LLM and fake tools):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install pyyaml pytest
pytest
```

---

## Deploy

```bash
databricks bundle deploy -t dev
```

This deploys the job and MLflow experiment defined in `resources/revenue_briefing.yml`.

**Targeting another workspace:** log in to it (`databricks auth login --host ...` or `--profile`). No code changes needed. Override defaults with variables:

```bash
databricks bundle deploy -t dev \
  --var catalog=my_catalog --var schema=my_schema --var llm_endpoint=my-endpoint
```

---

## Run

```bash
databricks bundle run revenue_briefing -t dev
```

Or interactively: open `notebooks/04_run_agentic.py` in Databricks and **Run all**. Change the `question` widget to try narrower questions (e.g. *"How are our leads doing?"*).

`notebooks/03_run_briefing.py` runs the original fixed pipeline (no LLM) for comparison.

---

## Project layout

```
databricks.yml                  # bundle: variables + targets (no workspace URL)
resources/revenue_briefing.yml  # job + MLflow experiment
config/settings.yaml            # catalog, thresholds, $ assumptions, LLM endpoint
agent/
  agentic.py                    # LLM tool-calling loop (+ fallback)
  registry.py                   # tool specs + dispatch
  llm.py                        # Databricks Model Serving client
  tools.py                      # 4 Spark SQL tools
  briefing.py                   # ranking/formatting + deterministic agent
notebooks/                      # data generator, exploration, agent demos
tests/                          # pytest (fake LLM)
docs/                           # how it works, pitch
```

---

## Team

Patrick + Tommy
