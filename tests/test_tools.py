from __future__ import annotations

from app.tools import load_tools, select_tool


def test_load_tools_from_db(build_seeded_repository):
    repository = build_seeded_repository()

    tools = load_tools(repository)

    assert len(tools) >= 2
    assert tools[0]["name"] == "run_sales_analysis"


def test_tool_selection_logic(build_seeded_repository):
    repository = build_seeded_repository()
    tools = load_tools(repository)

    selected = select_tool("Can you analyze the sales trend by region?", tools)

    assert selected is not None
    assert selected["name"] == "run_sales_analysis"
