# Step 1 — Generate synthetic data

## Do you need the zip file?

**No.** The notebook `notebooks/generate_synthetic_data.py` in this repo *is* the zip contents. Just use the repo.

## Instructions

1. In Databricks: **Workspace → Repos → Add Repo**
2. URL: `https://github.com/ptouhy/acm-xorbix-hackathon`
3. Open `notebooks/generate_synthetic_data.py`
4. **Run all cells** (serverless is fine)
5. Wait for the final cell — it prints row counts for all 8 tables

## Verify

Run a new SQL cell:

```sql
SHOW CATALOGS;
SHOW TABLES IN chiro_hackathon;
SELECT COUNT(*) FROM chiro_hackathon.patients;
```

If `workspace.chiro_hackathon` doesn't work, check what catalog `SHOW CATALOGS` returns and update `CATALOG = "..."` in the config cell of the notebook.

## What you just created

| Table | Business meaning |
|-------|------------------|
| `locations` | Clinic sites |
| `providers` | Chiropractors, therapists |
| `patients` | Customer roster (fake IDs only) |
| `leads` | People who might become patients |
| `appointments` | Booked visits (incl. no-shows) |
| `visits` | Completed visits + **revenue** |
| `referrals` | Word-of-mouth program |
| `marketing_campaigns` | Ad spend vs conversions |

When this works, tell your teammate: **"Step 1 done"** and we move to Step 2 (explore the data with simple SQL).
