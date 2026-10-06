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
