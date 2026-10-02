from acm_hackathon.settings import AgentSettings, ClinicSettings, DatabricksSettings


def test_agent_settings_load():
    s = AgentSettings.load()
    assert s.name == "clinic_growth_agent"
    assert "retention" in s.enabled_focus_areas


def test_clinic_settings_load():
    s = ClinicSettings.load()
    assert s.name == "AlignWell Chiropractic"
    assert len(s.services) >= 3


def test_databricks_table_fqn():
    s = DatabricksSettings.load()
    assert s.table_fqn("patients") == "workspace.chiro_hackathon.patients"
    assert s.table_fqn("visits") == "workspace.chiro_hackathon.visits"
