from __future__ import annotations

import pytest

from app.db import InMemoryRepository


@pytest.fixture
def build_seeded_repository():
    def _builder() -> InMemoryRepository:
        repository = InMemoryRepository()
        repository.seed_defaults()
        return repository

    return _builder
