from __future__ import annotations

from app.memory import retrieve_context, store_message


def test_store_message(build_seeded_repository):
    repository = build_seeded_repository()
    message = store_message(repository, 1, "user", "Please summarize the west region")

    assert message["id"] > 0
    assert repository.messages[-1]["content"] == "Please summarize the west region"
    assert repository.embeddings[-1]["message_id"] == message["id"]


def test_retrieve_context(build_seeded_repository):
    repository = build_seeded_repository()
    store_message(repository, 1, "user", "First follow-up")
    store_message(repository, 1, "assistant", "Second follow-up")

    context = retrieve_context(repository, 1, limit=3)

    assert len(context) == 3
    assert context[0]["content"] == "I can review the latest sales data and summarize the strongest region."
    assert context[-1]["content"] == "Second follow-up"
