from __future__ import annotations

import argparse
import sys
from pathlib import Path
from pprint import pprint

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent import Agent
from app.db import build_repository, PostgresRepository


def _print_mode_banner(repository: object) -> None:
    if isinstance(repository, PostgresRepository):
        print(f"[pg-agent] Connected to PostgreSQL at {repository.database_url.split('@')[-1]}")
    else:
        print("[pg-agent] Running with InMemoryRepository (DATABASE_URL not set — demo/fallback mode)")
    print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the PostgreSQL-powered AI agent demo entry point.")
    parser.add_argument("--user-id", default="cli-user", help="User identifier for the conversation.")
    parser.add_argument("--conversation-id", type=int, default=None, help="Existing conversation id.")
    parser.add_argument("--query", default="Show me the strongest sales region", help="User query to process.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repository = build_repository()
    _print_mode_banner(repository)
    agent = Agent(repository)
    result = agent.handle_query(args.user_id, args.query, conversation_id=args.conversation_id)
    pprint(result)


if __name__ == "__main__":
    main()
