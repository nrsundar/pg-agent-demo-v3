# PostgreSQL-Powered AI Agent Architecture

This repository is a conference demo that shows how PostgreSQL can act as the operational backbone for an AI agent. The project keeps agent memory, tool metadata, workflow state, and guardrail approvals in relational tables so the full system is easy to inspect, test, and extend.

## Problem Statement

Many agent demos hide state inside framework internals, temporary caches, or proprietary stores. That makes it difficult to explain how memory retrieval, tool choice, approval checks, and workflow state actually work.

This demo takes the opposite approach:

- PostgreSQL stores every important artifact.
- `pgvector` adds semantic memory support.
- The tool registry is data-driven instead of hard-coded.
- Workflow state is queryable and auditable.
- Guardrails are modeled as first-class records.

> **Note on LLM integration:** This demo uses keyword-based tool selection and templated responses — no API keys or language model calls required. This keeps the demo fully self-contained and the behavior deterministic during a live presentation. See [docs/extensions.md](docs/extensions.md) for how to wire in a real LLM and real embeddings.

## What The Demo Shows

- Conversation memory with message history and embedding records
- A database-driven tool registry
- Workflow state tracking for each request
- Approval guardrails for risky tool execution
- A simple orchestration layer that ties it all together

## Repository Layout

```text
pg-agent-demo/
├── README.md
├── requirements.txt
├── docker-compose.yml          ← one-command Postgres + pgvector setup
├── architecture/
│   ├── overview.md             ← agent flow diagram + table responsibilities
│   ├── memory.md
│   ├── tools.md
│   ├── state.md
│   └── guardrails.md
├── app/
│   ├── agent.py
│   ├── db.py
│   ├── main.py
│   ├── memory.py
│   ├── tools.py
│   └── workflow.py
├── db/
│   ├── schema.sql
│   ├── seed.sql
│   └── explanation.md
├── demo/
│   ├── run_demo.py
│   ├── demo_walkthrough.md     ← step-by-step guide with expected output
│   └── query_sheet.sql         ← ready-to-run psql queries for live inspection
├── docs/
│   ├── concepts.md             ← start here if you are new: agents, pgvector, embeddings explained
│   ├── reading_the_code.md     ← guided walkthrough of every file with explanations
│   ├── setup.md                ← Docker, existing Postgres, and no-Postgres paths
│   ├── how_it_works.md         ← complete step-by-step request trace with SQL at each step
│   ├── extensions.md           ← how to add real embeddings and LLM calls
│   └── production_considerations.md  ← what's needed for a real deployment
└── tests/
```

## Architecture Summary

The agent flow is intentionally small and readable:

1. A user query enters the agent.
2. The agent stores the message in PostgreSQL-backed memory.
3. Recent conversation context is retrieved.
4. Tools are loaded from the `tools_registry` table.
5. The agent selects a matching tool.
6. The selected tool runs against data in PostgreSQL.
7. Workflow state is updated as each step completes.
8. If a tool requires approval, an approval record is created before execution.
9. The assistant response is stored back into memory.

See [architecture/overview.md](architecture/overview.md) for the full flow diagram with table names at each step.

## How PostgreSQL Is Used

PostgreSQL is the system of record for the entire architecture:

- `conversations` and `messages` hold conversation history.
- `embeddings` stores vectorized memory entries using `pgvector`.
- `tools_registry` holds tool definitions and policies.
- `tool_calls` logs every tool invocation.
- `workflows` tracks request lifecycle state.
- `approvals` records guardrail decisions.
- `sales_data` provides sample business data for the demo tool.

Schema details live in [db/schema.sql](db/schema.sql) and [db/explanation.md](db/explanation.md).

## Quick Start

### Docker (recommended)

```bash
docker-compose up -d

# macOS / Linux
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/pg_agent_demo

# Windows (PowerShell)
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/pg_agent_demo"

pip install -r requirements.txt
python demo/run_demo.py
```

### No database required (in-memory fallback)

If `DATABASE_URL` is not set, the application **automatically falls back** to an in-memory repository that mirrors the seeded demo data. This is the safest option for workshops and conference environments.

```bash
pip install -r requirements.txt
python demo/run_demo.py
```

The startup output will clearly state which mode is active:
```
[pg-agent] Running with InMemoryRepository (DATABASE_URL not set — demo/fallback mode)
```
or
```
[pg-agent] Connected to PostgreSQL at localhost:5432/pg_agent_demo
```

For full setup options see [docs/setup.md](docs/setup.md).

## What To Observe

When you run the demo, look for these behaviors:

- Memory retrieval returns the recent conversation thread.
- Tool selection is based on tool metadata loaded from the database.
- Workflow status moves from `started` to `completed`.
- Tool calls are logged for auditability.
- Approval flow blocks execution when a tool requires review.

After running, inspect what was persisted using [demo/query_sheet.sql](demo/query_sheet.sql):

```bash
psql $DATABASE_URL -f demo/query_sheet.sql
```

## Testing Notes

The test suite uses the in-memory repository adapter so the repository is fast and deterministic in CI or on a laptop without a running PostgreSQL instance. The production code paths still include a PostgreSQL implementation that uses `psycopg` and expects the schema in `db/schema.sql`.

```bash
pytest
```

## Documentation Guide

### Conference session:
- [docs/abstract.md](docs/abstract.md) — full session abstract with demo-to-abstract mapping
- [docs/session_plan.md](docs/session_plan.md) — 50-minute timing plan, demo script, and pre-conference checklist

### New to AI agents or this project? Start here:
- [docs/concepts.md](docs/concepts.md) — what is an agent, the 4 pillars, pgvector, embeddings explained from scratch
- [docs/reading_the_code.md](docs/reading_the_code.md) — guided walkthrough of every file with explanations of why each decision was made

### Setup and running:
- [docs/setup.md](docs/setup.md) — Docker, existing Postgres, and no-Postgres setup paths
- [docs/how_it_works.md](docs/how_it_works.md) — complete step-by-step trace of a request through the system

### Architecture deep dives:
- [architecture/overview.md](architecture/overview.md) — flow diagram and table responsibilities
- [architecture/memory.md](architecture/memory.md) — episodic vs semantic memory, pgvector retrieval patterns
- [architecture/tools.md](architecture/tools.md) — data-driven tool registry, selection algorithm, audit log
- [architecture/state.md](architecture/state.md) — workflow state machine, observability queries
- [architecture/guardrails.md](architecture/guardrails.md) — approval model, why database records beat in-memory flags

### Live demo:
- [demo/demo_walkthrough.md](demo/demo_walkthrough.md) — step-by-step guide with expected terminal output
- [demo/query_sheet.sql](demo/query_sheet.sql) — ready-to-run psql queries for live audience inspection

### Going further:
- [docs/mock_embeddings.md](docs/mock_embeddings.md) — why mock embeddings are used and exact steps to replace with real ones
- [docs/extensions.md](docs/extensions.md) — how to add real embeddings and LLM calls
- [docs/production_considerations.md](docs/production_considerations.md) — RLS, connection pooling, audit logging, and more

## Conference Demo Talking Points

- PostgreSQL can be both the operational store and the observability surface for an agent.
- `pgvector` keeps semantic memory close to transactional state.
- Data-driven tool registries make tools inspectable and controllable.
- Guardrails are easier to explain when approvals live in tables.
- The same schema supports demos today and production hardening later.
- Everything the agent did is queryable with plain SQL — no separate observability system needed.
