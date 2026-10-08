"""Eval-harness logic tests (no Spark, no LLM)."""

from types import SimpleNamespace as NS

from agent.evals import CASES, calls_from_events, check_case, overall_pass_rate, run_eval

BY_ID = {c["id"]: c for c in CASES}


def call(tool, **args):
    return {"tool": tool, "args": args}


PLAN = call("record_plan")


def test_narrow_question_fails_when_extra_tools_are_called():
    case = BY_ID["leads_status"]
    assert check_case(case, [PLAN, call("find_stale_leads")]) == []
    fails = check_case(case, [PLAN, call("find_stale_leads"), call("find_churn_risk_patients")])
    assert fails == ["called forbidden find_churn_risk_patients"]


def test_argument_matching_catches_wrong_segment():
    case = BY_ID["churn_call"]
    good = [PLAN, call("find_churn_risk_patients"), call("draft_outreach", segment="churn_risk_patients")]
    bad = [PLAN, call("find_churn_risk_patients"), call("draft_outreach", segment="stale_leads")]
    assert check_case(case, good) == []
    assert "called forbidden draft_outreach(segment=stale_leads)" in check_case(case, bad)
    assert "missing draft_outreach(segment=churn_risk_patients)" in check_case(case, bad)


def test_any_of_and_off_topic_and_fallback():
    assert check_case(BY_ID["noshow_fix"], [PLAN, call("find_revenue_leaks")]) == []
    assert check_case(BY_ID["off_topic"], []) == []
    assert check_case(BY_ID["off_topic"], [call("find_stale_leads")]) == ["called tools on an off-topic question"]
    assert "fell back to deterministic briefing" in check_case(BY_ID["off_topic"], [], fell_back=True)


def test_calls_from_events_extracts_calls_errors_and_fallback():
    events = [NS(type="tool_call", data={"tool": "a", "args": {"x": 1}}),
              NS(type="tool_result", data={"tool": "a", "output": {"error": "boom"}}),
              NS(type="fallback", data={"reason": "endpoint down"})]
    assert calls_from_events(events) == ([{"tool": "a", "args": {"x": 1}}], "endpoint down", ["boom"])
    assert check_case(BY_ID["off_topic"], [], fell_back="endpoint down") == [
        "fell back to deterministic briefing: endpoint down"]


def test_guard_rejection_is_recoverable_and_not_a_failure():
    events = [NS(type="tool_call", data={"tool": "rank_actions", "args": {}}),
              NS(type="tool_result", data={"tool": "rank_actions", "output": {"error": "Nothing to rank yet. Call tools first."}})]
    calls, fell_back, errors = calls_from_events(events)
    assert errors == []
    assert check_case(BY_ID["noshow_fix"], [PLAN, call("find_revenue_leaks")], tool_errors=errors) == []
    assert check_case(BY_ID["noshow_fix"], [PLAN, call("find_revenue_leaks")], tool_errors=["SQL boom"]) == ["tool error: SQL boom"]


def test_run_eval_aggregates_pass_rates_and_survives_crashes():
    case = {"id": "t", "question": "q", "must": [{"tool": "a"}]}
    script = iter([[NS(type="tool_call", data={"tool": "a"})], [], RuntimeError("x")])

    class Agent:
        def run_stream(self, q):
            nxt = next(script)
            if isinstance(nxt, Exception):
                raise nxt
            return nxt

    res = run_eval(lambda: Agent(), [case], runs=3)
    assert res[0]["passes"] == 1 and res[0]["pass_rate"] == 0.33
    assert "crashed: RuntimeError" in res[0]["top_failures"]
    assert overall_pass_rate(res) == 0.333


def test_every_tool_using_case_requires_a_plan_but_off_topic_does_not():
    for c in CASES:
        has_plan = any(spec.get("tool") == "record_plan" for spec in c.get("must", []))
        assert has_plan == (not c.get("no_tools")), c["id"]
