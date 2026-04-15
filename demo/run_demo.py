from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent import Agent
from app.db import InMemoryRepository


def main() -> None:
    repository = InMemoryRepository()
    repository.seed_defaults()
    agent = Agent(repository)

    query = "Show me the strongest sales region this quarter"
    result = agent.handle_query("demo-user", query, conversation_id=1)

    print("=== PostgreSQL-Powered AI Agent Demo ===")
    print("Mode: In-memory repository (DATABASE_URL not set — safe fallback for demos)")
    print("Mode: In-memory repository with PostgreSQL-compatible behavior")
    print()
    print("Memory retrieval:")
    pprint(result["context"])
    print()
    print("Tool selection:")
    pprint(result["selected_tool"])
    print()
    print("Execution result:")
    pprint(result["tool_result"])
    print()
    print("Workflow state:")
    pprint(result["workflow"])
    print()
    print("Final response:")
    print(result["response"])


if __name__ == "__main__":
    main()
