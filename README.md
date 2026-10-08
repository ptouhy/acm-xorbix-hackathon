# Revenue Briefing Agent — ACM x Xorbix × UIowa Hackathon 2026

**An agentic AI that tells a chiropractic clinic what to do today to grow revenue.**

An LLM agent on **Databricks Free Edition** investigates clinic data across **leads**, **retention**, and **pricing**. It decides which analysis tools to call, then returns ranked actions with estimated dollar impact.

**Repo:** https://github.com/ptouhy/acm-xorbix-hackathon

---

## How it works

The agent follows the hackathon loop: **Observe → Reason → Decide → Act → Measure**.

```
question → LLM (Databricks Model Serving) ⇄ tools (Spark SQL on Unity Catalog)
                  ↓
   ranked actions + $ impact + "why" + today's call list + message
                  ↓
   MLflow run log  +  recommendation ledger (contacted vs holdout)  →  outcome check
   (falls back to a fixed pipeline if the LLM is unavailable)
```

| Step | Tools |
|------|-------|
| **Observe** (size the opportunity in $) | `find_stale_leads`, `find_top_lead_sources`, `find_churn_risk_patients`, `find_revenue_leaks` |
| **Reason** (why is it happening?) | `diagnose_no_shows`, `diagnose_lead_response` — they say so when a pattern is within random variation |
| **Decide** | `rank_actions` ranks the analysis results by estimated dollar impact (totals are computed in code, not by the LLM) |
| **Act** | `draft_outreach` builds today's prioritized contact list + message for stale leads or at-risk patients |
| **Measure** | MLflow run logs + `agent_recommendations` ledger (contacted vs. same-size holdout) + `src/notebooks/05_measure_outcomes.py` |

- The LLM **chooses** which tools to call: broad questions use several, narrow ones fewer, off-topic ones none.
- All dollar assumptions and thresholds live in `config/settings.yaml`, not in code.
- Details: [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) · Pitch: [docs/PITCH.md](docs/PITCH.md)

---

## Prerequisites

- A Databricks workspace (Free Edition works) with serverless compute
- A Model Serving endpoint that supports tool calling (default: `databricks-meta-llama-3-3-70b-instruct`; check **Serving** in your workspace)
- [Databricks CLI](https://docs.databricks.com/dev-tools/cli/install.html) v1.0.0+ (`brew install databricks/tap/databricks`)
- Python 3.10+ for local tests

No secrets or workspace URLs are stored in this repo. Authentication comes from your CLI profile.

---

## Setup

```bash
git clone https://github.com/ptouhy/acm-xorbix-hackathon.git
cd acm-xorbix-hackathon
databricks auth login --host https://<your-workspace>.cloud.databricks.com
```

The synthetic data is created by a job in the bundle (see **Run** below), so a new workspace needs no manual notebook steps.
(Optional: to browse or run notebooks interactively, add the repo as a Git folder: **Workspace → Create → Git folder** → paste the repo URL.)

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

This deploys two jobs (`setup_data`, `revenue_briefing`) and the MLflow experiment defined in `resources/revenue_briefing.yml`.

**Targeting another workspace:** log in to it (`databricks auth login --host ...` or `--profile`). No code changes needed. Override defaults with variables:

```bash
databricks bundle deploy -t dev \
  --var catalog=my_catalog --var schema=my_schema --var llm_endpoint=my-endpoint
```

---

## Run

```bash
databricks bundle run setup_data       -t dev   # once per workspace: creates 8 synthetic tables (takes a few minutes)
databricks bundle run revenue_briefing -t dev   # the agent, then the Measure step
```

The job has two tasks: `run_agentic_briefing` (notebook 04) then `measure_outcomes` (notebook 05).
Pass a different question with `--notebook-params question="..."`.

Or interactively: open `src/notebooks/04_run_agentic.py` in Databricks and **Run all**. Try:
- *"What should we focus on today to maximize revenue?"* (broad)
- *"How are our leads doing?"* (narrow: only lead tools)
- *"Why are we losing appointments to no-shows?"* (Reason tools)
- *"Which patients are about to leave and who should we call first?"* (Act: churn call list)

**Measure:** each outreach batch is saved to `<catalog>.<schema>.agent_recommendations` with a same-size
holdout. `src/notebooks/05_measure_outcomes.py` compares contacted vs. holdout (lead conversion / patient
retention) and reports the lift. The data is a static snapshot, so right after a run it shows the
baseline; re-run it after real outreach to get a verdict. MLflow logs every run under the bundle's experiment.

`src/notebooks/03_run_briefing.py` runs the original fixed pipeline (no LLM) for comparison.

---

## Project layout

```
README.md
databricks.yml                  # bundle: variables + targets (no workspace URL)
resources/revenue_briefing.yml  # jobs (setup_data, revenue_briefing) + MLflow experiment
src/
  agent/
    agentic.py                  # LLM tool-calling loop (+ fallback)
    registry.py                 # tool specs + dispatch
    llm.py                      # Databricks Model Serving client
    tools.py                    # Spark SQL tools: analysis, diagnostic (Reason), draft_outreach (Act)
    briefing.py                 # ranking/formatting + deterministic agent
    tracking.py                 # MLflow logging + recommendation ledger
    measure.py                  # contacted-vs-holdout outcome check
  notebooks/                    # exploration (02), fixed pipeline (03), agent demo (04), measure (05)
sample_data/
  generate_synthetic_data.py    # synthetic-data generator (8 Unity Catalog tables)
config/settings.yaml            # catalog, thresholds, $ assumptions, LLM endpoint
tests/                          # pytest (fake LLM, fake Spark)
docs/                           # how it works, pitch
```

---

## Team

Patrick + Tommy
