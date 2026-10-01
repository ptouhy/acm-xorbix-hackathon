from acm_hackathon.agents import ClinicGrowthAgent


def test_agent_retention_question():
    agent = ClinicGrowthAgent()
    response = agent.ask("Which patients are at risk of dropping off?")
    assert response.mode == "heuristic"
    assert len(response.tool_calls) >= 1
    assert "retention" in response.answer.lower() or "Re-engagement" in response.answer


def test_agent_pricing_question():
    agent = ClinicGrowthAgent()
    response = agent.ask("How should we optimize membership pricing?")
    assert any(c["focus_area"] == "pricing" for c in response.tool_calls)
