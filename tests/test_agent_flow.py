from __future__ import annotations

from app.agent import Agent


def test_full_agent_workflow(build_seeded_repository):
    repository = build_seeded_repository()
    agent = Agent(repository)

    result = agent.handle_query("demo-user", "Show me the strongest sales region", conversation_id=1)

    assert result["workflow"]["id"] > 0
    assert result["workflow"]["status"] == "completed"
    assert result["selected_tool"] is not None
    assert result["selected_tool"]["name"] == "run_sales_analysis"
    assert len(repository.tool_calls) == 1
    assert result["tool_result"] is not None
    assert result["response"]
