"""Eval-harness logic tests (no Spark, no LLM)."""

from types import SimpleNamespace as NS

from agent.evals import CASES, calls_from_events, check_case, overall_pass_rate, run_eval

BY_ID = {c["id"]: c for c in CASES}


def call(tool, **args):
    return {"tool": tool, "args": args}


def test_narrow_question_fails_when_extra_tools_are_called():
    case = BY_ID["leads_status"]
    assert check_case(case, [call("find_stale_leads")]) == []
    fails = check_case(case, [call("find_stale_leads"), call("find_churn_risk_patients")])
    assert fails == ["called forbidden find_churn_risk_patients"]


def test_argument_matching_catches_wrong_segment():
    case = BY_ID["churn_call"]
    good = [call("find_churn_risk_patients"), call("draft_outreach", segment="churn_risk_patients")]
    bad = [call("find_churn_risk_patients"), call("draft_outreach", segment="stale_leads")]
    assert check_case(case, good) == []
    assert "called forbidden draft_outreach(segment=stale_leads)" in check_case(case, bad)
    assert "missing draft_outreach(segment=churn_risk_patients)" in check_case(case, bad)


def test_any_of_and_off_topic_and_fallback():
    assert check_case(BY_ID["noshow_fix"], [call("find_revenue_leaks")]) == []
    assert check_case(BY_ID["off_topic"], []) == []
    assert check_case(BY_ID["off_topic"], [call("find_stale_leads")]) == ["called tools on an off-topic question"]
    assert "fell back to deterministic briefing" in check_case(BY_ID["off_topic"], [], fell_back=True)


def test_calls_from_events_extracts_calls_errors_and_fallback():
    events = [NS(type="tool_call", data={"tool": "a", "args": {"x": 1}}),
              NS(type="tool_result", data={"tool": "a", "output": {"error": "boom"}}),
              NS(type="fallback", data={})]
    assert calls_from_events(events) == ([{"tool": "a", "args": {"x": 1}}], True, 1)


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
    assert overall_pass_rate(res) == 0.333
