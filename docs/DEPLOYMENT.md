# Deployment (Databricks Asset Bundle)

## Prerequisites

- Databricks **Free Edition** workspace
- [Databricks CLI v0.218+](https://docs.databricks.com/dev-tools/cli/) with bundle support

```bash
databricks auth login --host https://YOUR-WORKSPACE.cloud.databricks.com
```

## Configure

1. Copy `.env.example` → `.env` and set `DATABRICKS_HOST`.
2. Edit `databricks.yml` variables if not using defaults (`main.clinic_hackathon`).

## Validate & deploy

```bash
databricks bundle validate
databricks bundle deploy -t dev
```

This syncs `config/`, `notebooks/`, and `src/` to your workspace and creates:

- Job: **`[dev] Clinic Growth Agent`** (setup → ingest → run agent)
- Experiment: **`/Shared/acm-xorbix-hackathon/clinic_growth_agent`**

## Run the pipeline

```bash
databricks bundle run clinic_agent_pipeline -t dev
```

Or run notebooks interactively on **serverless** in the workspace.

## Local development (no workspace)

```bash
source ~/.venvs/acm-xorbix-hackathon/bin/activate
pytest
python -c "
from acm_hackathon.agents import ClinicGrowthAgent
r = ClinicGrowthAgent().ask('Which patients are at risk?')
print(r.answer)
"
```

## Judging alignment

| Requirement | How we meet it |
|-------------|----------------|
| Agentic | Multi-tool agent with orchestrated tool calls |
| Databricks-centric | UC tables, serverless jobs, MLflow, Foundation Models |
| Deploy via DAB | `databricks.yml` bundle |
| Version control | Git repo, modular `src/` layout |
| Config separated | `config/*.yaml` |
| Testing | `pytest` suite |
| Documentation | README + `docs/` |
