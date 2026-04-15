from __future__ import annotations

from typing import Any, Dict, List


def store_message(repository: Any, conversation_id: int, role: str, content: str) -> Dict[str, Any]:
    """Store a message and a simple mock embedding for demo purposes."""
    embedding = [round(min(len(content), 10) / 10, 2), 0.5, round(len(role) / 10, 2)]
    return repository.store_message(conversation_id, role, content, embedding)


def retrieve_context(repository: Any, conversation_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    """Return the recent conversation history in chronological order."""
    return repository.get_recent_messages(conversation_id, limit=limit)
