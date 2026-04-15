from __future__ import annotations

from typing import Any, Dict, List, Optional


def load_tools(repository: Any) -> List[Dict[str, Any]]:
    """Read tool metadata from the repository-backed tool registry."""
    return repository.load_tools()


def select_tool(query: str, tools: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Choose the tool whose keywords best match the incoming query."""
    normalized_query = query.lower()
    best_tool: Optional[Dict[str, Any]] = None
    best_score = 0

    for tool in tools:
        keywords = [keyword.strip() for keyword in tool["keyword_hint"].split(",") if keyword.strip()]
        score = sum(1 for keyword in keywords if keyword in normalized_query)
        if score > best_score:
            best_score = score
            best_tool = tool

    if best_tool is not None:
        return best_tool

    for tool in tools:
        if any(token in normalized_query for token in tool["name"].lower().split("_")):
            return tool

    return None
