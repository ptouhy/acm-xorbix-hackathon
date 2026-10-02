"""Tests for rank_actions and format_briefing (no Spark needed)."""

from agent.briefing import format_briefing, rank_actions


def test_rank_actions_sorts_by_impact():
    tools = [
        {"focus": "leads", "tool": "a", "estimated_impact_usd": 1000, "recommendation": "A", "metrics": {}},
        {"focus": "retention", "tool": "b", "estimated_impact_usd": 5000, "recommendation": "B", "metrics": {}},
        {"focus": "pricing", "tool": "c", "estimated_impact_usd": 3000, "recommendation": "C", "metrics": {}},
    ]
    ranked = rank_actions(tools)
    assert ranked[0]["tool"] == "b"
    assert ranked[0]["rank"] == 1


def test_format_briefing_includes_total():
    actions = [{"rank": 1, "focus": "leads", "tool": "t", "estimated_impact_usd": 1000, "recommendation": "Do X", "metrics": {}}]
    text = format_briefing("Test?", actions, 1000)
    assert "Revenue Briefing Agent" in text
    assert "$1,000" in text
