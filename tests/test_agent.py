from app.ai.migration_advisor import MigrationAdvisor, MigrationAdvisorConfig


def test_agent_builds_without_api_call(tmp_path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Use tools. Cite evidence. Never write.", encoding="utf-8")
    agent = MigrationAdvisor(MigrationAdvisorConfig(
        model="gpt-5.6-terra", database_path=tmp_path / "audit.db",
        instructions_path=prompt,
    )).build()
    assert agent.name == "Migration Copilot"
    assert len(agent.tools) == 1

