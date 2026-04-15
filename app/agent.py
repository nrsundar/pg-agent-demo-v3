from __future__ import annotations

from typing import Any, Dict, Optional

from app.memory import retrieve_context, store_message
from app.tools import load_tools, select_tool
from app.workflow import create_workflow, update_workflow


class Agent:
    """Coordinates memory retrieval, tool selection, workflow tracking, and guardrails."""

    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def handle_query(self, user_id: str, query: str, conversation_id: Optional[int] = None) -> Dict[str, Any]:
        if conversation_id is None:
            conversation_id = self.repository.create_conversation(user_id, "Ad hoc agent session")

        workflow = create_workflow(self.repository, conversation_id, query)
        store_message(self.repository, conversation_id, "user", query)
        context = retrieve_context(self.repository, conversation_id)

        tools = load_tools(self.repository)
        tool = select_tool(query, tools)
        if tool is None:
            response = "I could not find a matching tool for that request."
            store_message(self.repository, conversation_id, "assistant", response)
            workflow = update_workflow(self.repository, workflow["id"], "completed", response)
            return {
                "conversation_id": conversation_id,
                "workflow": workflow,
                "context": context,
                "selected_tool": None,
                "tool_result": None,
                "response": response,
            }

        if tool["requires_approval"]:
            approval = self.repository.create_approval(
                workflow["id"],
                tool["name"],
                "Tool flagged as approval-required by policy.",
            )
            response = f"Approval required before running {tool['name']}. Approval status: {approval['status']}."
            store_message(self.repository, conversation_id, "assistant", response)
            workflow = update_workflow(self.repository, workflow["id"], "awaiting_approval", response)
            return {
                "conversation_id": conversation_id,
                "workflow": workflow,
                "context": context,
                "selected_tool": tool,
                "tool_result": None,
                "response": response,
                "approval": approval,
            }

        tool_result = self.repository.execute_tool(tool, query)
        self.repository.log_tool_call(
            workflow["id"],
            tool["name"],
            {"query": query, "conversation_id": conversation_id},
            tool_result,
        )

        response = self._compose_response(context, tool, tool_result)
        store_message(self.repository, conversation_id, "assistant", response)
        workflow = update_workflow(self.repository, workflow["id"], "completed", response)

        return {
            "conversation_id": conversation_id,
            "workflow": workflow,
            "context": context,
            "selected_tool": tool,
            "tool_result": tool_result,
            "response": response,
        }

    def _compose_response(self, context: Any, tool: Dict[str, Any], tool_result: Dict[str, Any]) -> str:
        prior_turns = max(len(context) - 1, 0)
        return (
            f"Using tool {tool['name']}, I reviewed {prior_turns} earlier message(s). "
            f"{tool_result['summary']}"
        )
