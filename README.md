# ACM x Xorbix × UIowa Hackathon 2026 — Clinic Growth Agent

**Agentic AI solution on Databricks Free Edition** for a boutique chiropractic business scaling toward $250M ARR.

**Public repo:** https://github.com/ptouhy/acm-xorbix-hackathon

| | |
|---|---|
| **Dates** | Oct 1 kickoff → Oct 8 demo (Seamans, Engineering Building) |
| **Platform** | Databricks Free Edition (serverless) |
| **Data** | `workspace.chiro_hackathon.*` (official synthetic dataset) |
| **Deploy** | Databricks Asset Bundles (DAB) |

## What this builds

An agent that **reasons over clinic data** and recommends actions across:

1. **Leads** — funnel analysis, lead scoring, speed-to-lead
2. **Retention** — churn-risk patients, inactivity, no-show rates
3. **Pricing** — revenue by service, package mix, marketing ROI

## Prerequisites (you've done step 1 ✓)

- [x] Databricks Free Edition workspace
- [x] Run `notebooks/generate_synthetic_data.py` → 8 tables populated
- [ ] Deploy this repo via DAB
- [ ] Run `notebooks/02_run_agent.py` and demo
- [ ] Prepare 2-minute elevator pitch

## Deploy & run on Databricks

```bash
# Local — authenticate once
databricks auth login --host https://YOUR-WORKSPACE.cloud.databricks.com

# Deploy bundle (syncs config, src, notebooks)
databricks bundle validate
databricks bundle deploy -t dev

# Run the agent job
databricks bundle run clinic_agent_pipeline -t dev
```

Or open **`notebooks/02_run_agent.py`** in the workspace and run interactively.

### Bundle variables (`databricks.yml`)

| Variable | Default | Notes |
|----------|---------|-------|
| `catalog` | `workspace` | Run `SHOW CATALOGS` if different |
| `schema` | `chiro_hackathon` | From synthetic data notebook |

## Local development

```bash
source ~/.venvs/acm-xorbix-hackathon/bin/activate
pytest
python -c "
from acm_hackathon.agents import ClinicGrowthAgent
from acm_hackathon.data.sample_data import all_sample_tables
print(ClinicGrowthAgent(tables=all_sample_tables()).ask('Which leads should we prioritize?').answer)
"
```

## Project layout

```
config/                    # YAML — prompts, UC targets (no secrets)
notebooks/
  generate_synthetic_data.py   # Official data generator (already run)
  02_run_agent.py              # Main demo notebook
src/acm_hackathon/
  agents/                  # Orchestrator + focus-area tools
  data/loader.py           # Spark SQL → agent tables
databricks.yml             # DAB — deploy to any workspace via config
docs/                      # Architecture & deployment guides
```

## Judging checklist

| Criterion | How we address it |
|-----------|-------------------|
| Business Impact | Quantified recoverable revenue, conversion rates, no-show impact |
| Technical Innovation | Multi-tool agent over 8-table UC dataset |
| Prototype Quality | Runnable notebook + DAB job |
| Pitch & Development | Public repo + DAB + README |

## Team setup (Tommy)

```bash
git clone https://github.com/ptouhy/acm-xorbix-hackathon.git
cd acm-xorbix-hackathon
./scripts/setup.sh
databricks auth login --host https://YOUR-WORKSPACE.cloud.databricks.com
```

## Next steps

1. **Deploy** — `databricks bundle deploy -t dev`
2. **Demo** — run `02_run_agent.py` with a hero question
3. **Pick your pitch angle** — one workflow (e.g. retention + revenue recovery)
4. **Optional** — set `use_model=true` for Foundation Model synthesis
5. **Oct 8** — 2-min pitch: problem → solution → how built on Databricks
