"""
Tool-selection eval — does the agent pick the right tools for each kind of question?

STEP EXPLANATION:
  An LLM agent is non-deterministic, so one good run proves little. Each case below states which
  tools a good run MUST call and which it must NOT call (arguments included). run_eval() repeats
  every case N times on the real agent and reports pass rates plus the most common failure.
  A call spec is {"tool": name, "args": {...}} (args optional, matched as a subset) or
  {"any": [name, ...]}.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable, Iterable

CASES: list[dict] = [
    {"id": "broad", "question": "What should we focus on today to maximize revenue?",
     "must": [{"tool": "find_stale_leads"}, {"tool": "find_churn_risk_patients"},
              {"tool": "find_revenue_leaks"}, {"tool": "rank_actions"}, {"tool": "draft_outreach"}]},
    {"id": "leads_status", "question": "How are our leads doing?",
     "must": [{"tool": "find_stale_leads"}],
     "must_not": [{"tool": "find_churn_risk_patients"}, {"tool": "find_revenue_leaks"}, {"tool": "diagnose_no_shows"}]},
    {"id": "leads_why", "question": "Why aren't our leads converting?",
     "must": [{"tool": "diagnose_lead_response"}],
     "must_not": [{"tool": "find_churn_risk_patients"}, {"tool": "find_revenue_leaks"}]},
    {"id": "noshow_why", "question": "Why are we losing appointments to no-shows?",
     "must": [{"tool": "diagnose_no_shows"}],
     "must_not": [{"tool": "find_churn_risk_patients"}, {"tool": "find_stale_leads"}]},
    {"id": "noshow_fix", "question": "How can we reduce no-shows?",
     "must": [{"any": ["diagnose_no_shows", "find_revenue_leaks"]}],
     "must_not": [{"tool": "find_stale_leads"}, {"tool": "find_churn_risk_patients"}]},
    {"id": "churn_call", "question": "Which patients are about to leave and who should we call first?",
     "must": [{"tool": "find_churn_risk_patients"},
              {"tool": "draft_outreach", "args": {"segment": "churn_risk_patients"}}],
     "must_not": [{"tool": "draft_outreach", "args": {"segment": "stale_leads"}}]},
    {"id": "lead_call", "question": "Give me a list of leads to follow up with today.",
     "must": [{"tool": "draft_outreach", "args": {"segment": "stale_leads"}}],
     "must_not": [{"tool": "draft_outreach", "args": {"segment": "churn_risk_patients"}}]},
    {"id": "marketing", "question": "Are we wasting money on marketing?",
     "must": [{"tool": "find_revenue_leaks"}],
     "must_not": [{"tool": "find_churn_risk_patients"}, {"tool": "draft_outreach"}]},
    {"id": "retention_status", "question": "How is patient retention looking?",
     "must": [{"tool": "find_churn_risk_patients"}],
     "must_not": [{"tool": "find_stale_leads"}, {"tool": "find_revenue_leaks"}]},
    {"id": "off_topic", "question": "What is the weather today?", "no_tools": True},
]


PLAN = {"tool": "record_plan"}
for _case in CASES:  # every tool-using case should start with a recorded plan
    if not _case.get("no_tools"):
        _case["must"] = [PLAN] + _case.get("must", [])


def _matches(spec: dict, call: dict) -> bool:
    if "any" in spec:
        return call["tool"] in spec["any"]
    if call["tool"] != spec["tool"]:
        return False
    want = spec.get("args", {})
    return all(call["args"].get(k) == v for k, v in want.items())


def _label(spec: dict) -> str:
    if "any" in spec:
        return " or ".join(spec["any"])
    args = spec.get("args")
    return spec["tool"] + (f"({', '.join(f'{k}={v}' for k, v in args.items())})" if args else "")


# Rejections the agent is designed to recover from (it then runs an analysis tool). Not failures.
RECOVERABLE_ERRORS = ("Nothing to rank yet",)


def check_case(case: dict, calls: list[dict], fell_back: bool | str = False, tool_errors: list[str] | None = None) -> list[str]:
    """Return a list of failure reasons (empty = pass)."""
    failures = []
    if fell_back:
        reason = f": {str(fell_back)[:90]}" if isinstance(fell_back, str) else ""
        failures.append(f"fell back to deterministic briefing{reason}")
    if case.get("no_tools"):
        if calls:
            failures.append("called tools on an off-topic question")
        return failures
    for spec in case.get("must", []):
        if not any(_matches(spec, c) for c in calls):
            failures.append(f"missing {_label(spec)}")
    for spec in case.get("must_not", []):
        if any(_matches(spec, c) for c in calls):
            failures.append(f"called forbidden {_label(spec)}")
    for msg in tool_errors or []:
        failures.append(f"tool error: {msg[:90]}")
    return failures


def calls_from_events(events: Iterable[Any]) -> tuple[list[dict], bool | str, list[str]]:
    """Pull (tool calls, fallback reason or False, unrecovered tool error messages) out of AgentEvents."""
    calls, fell_back, errors = [], False, []
    for e in events:
        if e.type == "tool_call":
            calls.append({"tool": e.data["tool"], "args": e.data.get("args") or {}})
        elif e.type == "tool_result" and "error" in e.data["output"]:
            msg = str(e.data["output"]["error"])
            if not msg.startswith(RECOVERABLE_ERRORS):
                errors.append(msg)
        elif e.type == "fallback":
            fell_back = e.data.get("reason") or True
    return calls, fell_back, errors


def run_eval(make_agent: Callable[[], Any], cases: list[dict], runs: int,
             on_run: Callable[[str, int, list[str]], None] | None = None) -> list[dict]:
    """Run every case `runs` times. Returns one summary dict per case."""
    results = []
    for case in cases:
        failure_counts: Counter = Counter()
        passes = 0
        for i in range(runs):
            try:
                calls, fell_back, errors = calls_from_events(make_agent().run_stream(case["question"]))
                failures = check_case(case, calls, fell_back, errors)
            except Exception as exc:  # a crashed run counts as a failure
                failures = [f"crashed: {type(exc).__name__}"]
            passes += not failures
            failure_counts.update(failures)
            if on_run:
                on_run(case["id"], i, failures)
        results.append({
            "case": case["id"], "question": case["question"], "runs": runs, "passes": passes,
            "pass_rate": round(passes / runs, 2),
            "top_failures": "; ".join(f"{m} (x{n})" for m, n in failure_counts.most_common(3)),
        })
    return results


def overall_pass_rate(results: list[dict]) -> float:
    total = sum(r["runs"] for r in results)
    return round(sum(r["passes"] for r in results) / total, 3) if total else 0.0
