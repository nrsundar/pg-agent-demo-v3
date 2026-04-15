from __future__ import annotations

from app.workflow import create_workflow, update_workflow


def test_workflow_creation(build_seeded_repository):
    repository = build_seeded_repository()

    workflow = create_workflow(repository, 1, "Show me the strongest region")

    assert workflow["id"] > 0
    assert workflow["status"] == "started"


def test_workflow_status_updates(build_seeded_repository):
    repository = build_seeded_repository()
    workflow = create_workflow(repository, 1, "Show me the strongest region")

    updated = update_workflow(repository, workflow["id"], "completed", "Finished")

    assert updated["status"] == "completed"
    assert updated["last_message"] == "Finished"
