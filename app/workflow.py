from __future__ import annotations

from typing import Any, Dict


def create_workflow(repository: Any, conversation_id: int, query_text: str) -> Dict[str, Any]:
    """Start a workflow record for the incoming request."""
    return repository.create_workflow(conversation_id, query_text, status="started")


def update_workflow(repository: Any, workflow_id: int, status: str, last_message: str) -> Dict[str, Any]:
    """Persist the latest workflow state transition."""
    return repository.update_workflow(workflow_id, status, last_message)
