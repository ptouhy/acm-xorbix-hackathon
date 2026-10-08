# 2-minute pitch — Revenue Briefing Agent

## Business problem (0:00–0:40)

Our clinic network has to grow from **$100M to $250M ARR**. Growth stalls in places nobody sees on a dashboard: **leads go cold**, **patients quietly leave**, and **appointments are missed**. Our synthetic network has 45,000 leads, 60,000 patients and 350,000 appointments. In one snapshot we find **570 leads that went quiet in the last month** (plus 2,700 dormant ones worth a win-back), **5,800 active patients who stopped visiting 2 to 6 months ago**, and about **8,800 no-shows in the last year** (10%). A manager can't work through that by hand each morning. They need to know **what to do today and what it's worth**.

## Solution (0:40–1:30)

The **Revenue Briefing Agent** is an LLM that works through the question the way an analyst would: **Observe → Reason → Decide → Act → Measure**.

- **Plan and observe:** it states a short plan, then chooses its own tools. Ask a broad question and it sizes leads, retention and pricing. Ask a narrow one and it uses only what it needs.
- **Reason:** diagnostic tools explain *why*. They also say so when a pattern is just noise. For example, response time had no statistically meaningful effect on conversion, so the agent doesn't recommend an SLA.
- **Decide:** it ranks actions by estimated dollar impact. The totals are computed in code, never by the LLM.
- **Act:** it builds today's call list, the warmest leads or the most loyal lapsing patients, with a ready-to-send message, and **stages it in an outreach queue** where staff approve it. The agent acts; a human signs off.
- **Measure:** every list is saved with a same-size **holdout group**. After outreach, the agent compares contacted vs. holdout to check whether it worked.

**Live demo:** ask *"What should we focus on today?"*, then *"Which patients are about to leave and who should we call first?"*

## How it was built (1:30–2:00)

- **Databricks Free Edition:** Unity Catalog for the synthetic data, Spark SQL tools, Model Serving for the LLM's tool calling, MLflow for run tracking.
- **Declarative Automation Bundle:** one `databricks bundle deploy` ships the two-task job (agent, then measure) and the MLflow experiment. Another workspace needs configuration changes only, with no workspace URLs in the code.
- **Reliable by design:** it falls back to a fixed pipeline if the LLM is down, and an eval harness (10 questions × 5 runs) measures how often it picks the right tools, and the unit tests cover the loop and the tools.

---

## If a judge asks

- **"Why are the lead numbers so small?"** We only count leads that are still actionable: 3 to 30 days old at full conversion odds, 31 to 180 days as a win-back at lower odds. Our first version counted 26,900 "stale" leads, but most were over a year old, so we cut them.
- **"Is the pricing number inflated?"** We price only what the data supports: the last 12 months of no-shows at the measured $96 per visit, with a 30% recovery assumption. We dropped a package-upsell estimate because Package Plan visits earn the same as every other payment type.
- **"Are the dollar figures real?"** They are estimates from configurable assumptions in `config/settings.yaml` (visit value, conversion rate and so on) applied to synthetic data. Change an assumption and the numbers move.
- **"Did it actually work?"** The data is a static snapshot, so today the check shows the baseline. The holdout design is what gives a real answer once outreach happens. It's the same loop a production deployment would run.
- **"Why didn't it find a no-show driver?"** Our synthetic no-shows are evenly spread, and the agent says so instead of inventing a pattern.
- **"How does it scale?"** Tools are parameterized by catalog and schema. More locations means more rows in the same tables, and new questions mean adding a tool.

## Demo numbers (replace with your live run)

Total opportunity about **$0.84M**: retention about $0.56M, pricing (no-shows) about $0.25M a year, leads about $0.03M. That's roughly 14% of the data's $6.1M trailing-12-month revenue.
