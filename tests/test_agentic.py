"""Agent-loop tests using a scripted fake LLM and monkeypatched tools (no Spark, no network)."""

import pytest

from agent import agentic
from agent.agentic import AgenticBriefingAgent


class FakeLLM:
    """Replays scripted replies, one per chat() call."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def chat(self, messages, tools=None):
        self.calls += 1
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def call(name, id_="1"):
    return {"id": id_, "name": name, "arguments": {}}


def say(text):
    return {"content": text, "tool_calls": []}


def use(*calls):
    return {"content": None, "tool_calls": list(calls)}


@pytest.fixture(autouse=True)
def fake_tools(monkeypatch):
    outputs = {
        "find_stale_leads": {"tool": "find_stale_leads", "focus": "leads", "estimated_impact_usd": 1000,
                             "recommendation": "Call leads", "metrics": {}},
        "find_churn_risk_patients": {"tool": "find_churn_risk_patients", "focus": "retention",
                                     "estimated_impact_usd": 5000, "recommendation": "Re-engage", "metrics": {}},
    }
    monkeypatch.setattr(agentic, "run_spark_tool", lambda name, *a: outputs[name])


def make_agent(replies):
    return AgenticBriefingAgent(spark=None, llm=FakeLLM(replies))


def test_llm_picks_only_needed_tools_and_answers():
    agent = make_agent([use(call("find_stale_leads")), say("Call your stale leads.")])
    result = agent.run("How are our leads?")
    assert [t["tool"] for t in result.trace if t["type"] == "tool_call"] == ["find_stale_leads"]
    assert result.briefing_text == "Call your stale leads."
    assert result.actions[0]["tool"] == "find_stale_leads"


def test_ranks_by_impact_across_tools():
    agent = make_agent([
        use(call("find_stale_leads", "1"), call("find_churn_risk_patients", "2")),
        say("done"),
    ])
    result = agent.run("What should we focus on?")
    assert result.actions[0]["tool"] == "find_churn_risk_patients"
    assert result.total_estimated_impact_usd == 6000


def test_rank_tool_returns_code_computed_total():
    agent = make_agent([
        use(call("find_stale_leads", "1"), call("find_churn_risk_patients", "2")),
        use(call("rank_actions", "3")),
        say("done"),
    ])
    result = agent.run("q")
    ranked = next(t["output"] for t in result.trace if t["tool"] == "rank_actions" and t["type"] == "tool_result")
    assert ranked["total_estimated_impact_usd"] == 6000


def test_rank_before_any_tool_returns_error_and_llm_recovers():
    agent = make_agent([
        use(call("rank_actions", "1")),
        use(call("find_stale_leads", "2")),
        say("done"),
    ])
    result = agent.run("q")
    first = next(t["output"] for t in result.trace if t["type"] == "tool_result")
    assert "error" in first
    assert result.actions[0]["tool"] == "find_stale_leads"


def test_tool_arguments_are_passed_and_cached_per_argument_set(monkeypatch):
    seen = []

    def fake(name, spark, catalog, schema, settings, args=None):
        seen.append((name, args))
        return {"tool": name, "kind": "action", "focus": "leads", "estimated_impact_usd": 10,
                "recommendation": "r", "targets": [], "message_template": "m",
                "metrics": {"segment": args["segment"], "segment_size": 1, "batch_size": 0}}

    monkeypatch.setattr(agentic, "run_spark_tool", fake)
    a = {"segment": "stale_leads"}
    b = {"segment": "churn_risk_patients"}
    agent = make_agent([
        use({"id": "1", "name": "draft_outreach", "arguments": a}),
        use({"id": "2", "name": "draft_outreach", "arguments": a},
            {"id": "3", "name": "draft_outreach", "arguments": b}),
        say("done"),
    ])
    agent.run("q")
    assert seen == [("draft_outreach", a), ("draft_outreach", b)]  # second call to `a` was cached


def test_duplicate_call_is_cached_and_unknown_tool_is_reported():
    agent = make_agent([
        use(call("find_stale_leads", "1")),
        use(call("find_stale_leads", "2"), call("nope", "3")),
        say("done"),
    ])
    result = agent.run("q")
    outputs = {t["tool"]: t["output"] for t in result.trace if t["type"] == "tool_result"}
    assert "error" in outputs["nope"]
    assert len(result.tool_outputs) == 1  # stale leads only counted once


def test_llm_failure_falls_back_to_deterministic_agent(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(AgenticBriefingAgent, "_fallback", lambda self, q: sentinel)
    events = list(make_agent([RuntimeError("endpoint down")]).run_stream("q"))
    assert events[-1].type == "fallback"
    assert events[-1].data["result"] is sentinel
    assert "endpoint down" in events[-1].data["reason"]


def test_stops_at_max_steps_and_still_returns_ranked_result():
    agent = make_agent([use(call("find_stale_leads", str(i))) for i in range(10)])
    agent.max_steps = 3
    result = agent.run("q")
    assert agent.llm.calls == 3
    assert result.actions  # formatted deterministically since LLM never gave a final answer


def test_final_briefing_appends_diagnostics_and_outreach(monkeypatch):
    outs = {
        "find_stale_leads": {"tool": "find_stale_leads", "focus": "leads", "estimated_impact_usd": 1000,
                             "recommendation": "Call", "metrics": {}},
        "diagnose_no_shows": {"tool": "diagnose_no_shows", "kind": "diagnostic", "focus": "pricing",
                              "estimated_impact_usd": 0, "recommendation": "Evenly spread.", "metrics": {}},
        "draft_outreach": {"tool": "draft_outreach", "kind": "action", "focus": "leads",
                           "estimated_impact_usd": 30, "recommendation": "Contact 1 of 5.",
                           "metrics": {"segment": "stale_leads", "segment_size": 5, "batch_size": 1},
                           "message_template": "Hi {first_name}!",
                           "targets": [{"lead_id": "LD1", "source": "Referral"}]},
    }
    monkeypatch.setattr(agentic, "run_spark_tool", lambda name, *a: outs[name])
    agent = make_agent([
        use(call("find_stale_leads", "1"), call("diagnose_no_shows", "2"), call("draft_outreach", "3")),
        say("Headline."),
    ])
    text = agent.run("q").briefing_text
    assert text.startswith("Headline.")
    assert "## Why (diagnostics)" in text and "Evenly spread." in text
    assert "Hi {first_name}!" in text and "LD1" in text


def test_off_topic_reply_without_figures_passes_through():
    result = make_agent([say("I can help with leads, retention and no-shows.")]).run("What is the weather?")
    assert result.briefing_text.startswith("I can help")
    assert result.actions == []


def test_untooled_answer_with_numbers_falls_back(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(AgenticBriefingAgent, "_fallback", lambda self, q: sentinel)
    events = list(make_agent([say("You will make $500,000 today.")]).run_stream("q"))
    assert events[-1].type == "fallback" and events[-1].data["result"] is sentinel


def test_plan_is_recorded_shown_and_prepended_to_the_briefing():
    plan_call = {"id": "p", "name": "record_plan", "arguments": {"steps": ["size leads", "draft outreach"]}}
    agent = make_agent([use(plan_call, call("find_stale_leads", "1")), say("Done.")])
    events = list(agent.run_stream("q"))
    assert [e.data["steps"] for e in events if e.type == "plan"] == [["size leads", "draft outreach"]]
    assert events[-1].data["result"].briefing_text.startswith("**Plan:** size leads → draft outreach")
