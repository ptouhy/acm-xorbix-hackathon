# ACM x Xorbix Hackathon 2026 — Clinic Growth Agent

**Agentic AI solution on Databricks Free Edition** for a chiropractic clinic seeking higher revenue and profit margin.

| | |
|---|---|
| **Dates** | Oct 1 – 8, 2026 |
| **Platform** | Databricks Free Edition |
| **Deploy** | Databricks Asset Bundles (DAB) |
| **Team size** | 1–2 members |

## Challenge

Build an agent that addresses one or more strategic focus areas:

1. **Leads** — attract, qualify, and convert new patients
2. **Retention** — reduce drop-off and improve care plan completion
3. **Pricing** — optimize services, packages, and memberships

This repo implements **all three** as modular agent tools; enable/disable focus areas in `config/agent.yaml`.

## Quick start

```bash
chmod +x scripts/setup.sh && ./scripts/setup.sh
source ~/.venvs/acm-xorbix-hackathon/bin/activate
pytest
```

Try the agent locally:

```python
from acm_hackathon.agents import ClinicGrowthAgent

agent = ClinicGrowthAgent()
print(agent.ask("Which patients are at risk of dropping off?").answer)
```

## Project layout

```
config/                 # YAML config (prompts, clinic profile, UC targets)
src/acm_hackathon/
  agents/               # Orchestrator + focus-area tools
  data/                 # Schemas + sample clinic data
notebooks/              # Databricks notebooks (deployed via DAB)
docs/                   # Architecture & deployment guides
databricks.yml          # Asset bundle definition
tests/                  # pytest suite
```

## Deploy to Databricks Free Edition

```bash
databricks auth login --host "$DATABRICKS_HOST"
databricks bundle validate
databricks bundle deploy -t dev
databricks bundle run clinic_agent_pipeline -t dev
```

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Configuration

| File | Purpose |
|------|---------|
| `config/agent.yaml` | System prompt, model endpoint, enabled focus areas |
| `config/clinic.yaml` | Clinic name, services, memberships |
| `config/databricks.yaml` | Unity Catalog catalog/schema/table names |

## Engineering practices

- **Version control** — git + modular Python package
- **Config separated from code** — all prompts/settings in YAML
- **Testing** — `pytest` for tools, settings, and agent routing
- **Documentation** — README + architecture/deployment docs

## Notes

- Free Edition is **serverless-only**; jobs in `databricks.yml` use serverless environments.
- Sample data is synthetic — replace with Unity Catalog tables for your demo.
- Set `use_model=true` in notebook `02_run_agent` to use a Foundation Model endpoint.
