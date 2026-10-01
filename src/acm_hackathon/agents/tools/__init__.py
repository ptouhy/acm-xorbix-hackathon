"""Agent tools grouped by strategic focus area."""

from __future__ import annotations

import pandas as pd

from acm_hackathon.agents.tools import leads, pricing, retention
from acm_hackathon.agents.tools.base import ToolDefinition
from acm_hackathon.settings import AgentSettings, ClinicSettings


def build_tool_registry(
    tables: dict[str, pd.DataFrame],
    agent_settings: AgentSettings | None = None,
    clinic_settings: ClinicSettings | None = None,
) -> dict[str, ToolDefinition]:
    """Register enabled tools and bind clinic data."""
    agent_settings = agent_settings or AgentSettings.load()
    clinic_settings = clinic_settings or ClinicSettings.load()

    leads.bind_data(tables)
    retention.bind_data(tables)
    pricing.bind_data(tables)

    all_tools: list[ToolDefinition] = []
    if "leads" in agent_settings.enabled_focus_areas:
        all_tools.extend(leads.get_lead_tools())
    if "retention" in agent_settings.enabled_focus_areas:
        all_tools.extend(retention.get_retention_tools())
    if "pricing" in agent_settings.enabled_focus_areas:
        all_tools.extend(
            pricing.get_pricing_tools(memberships=list(clinic_settings.memberships))
        )

    return {t.name: t for t in all_tools}
