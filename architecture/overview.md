# Architecture Overview

The demo uses PostgreSQL as a unified control plane for an AI agent.

## Agent Flow

Every query passes through 9 steps. Each step reads from or writes to a specific PostgreSQL table.

```
User Query
    │
    ▼
┌─────────────────────────────────┐
│  1. Store user message          │──► messages
│  2. Generate embedding          │──► embeddings
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│  3. Retrieve conversation       │◄── messages
│     context (last 5 messages)   │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│  4. Load tools from registry    │◄── tools_registry
│  5. Select best matching tool   │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│  6. Guardrail check             │──► approvals (if requires_approval)
│     requires_approval?          │    workflow status → awaiting_approval
└─────────────────────────────────┘
    │ (approved or not required)
    ▼
┌─────────────────────────────────┐
│  7. Execute tool                │◄── sales_data (or other domain tables)
│  8. Log tool call               │──► tool_calls
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│  9. Update workflow state       │──► workflows (status → completed)
│     Store assistant response    │──► messages
└─────────────────────────────────┘
    │
    ▼
Response returned to caller
```

## Table Responsibilities

| Table | Pillar | Purpose |
|---|---|---|
| `conversations` | Memory | Groups messages into a session |
| `messages` | Memory | Stores full conversation transcript |
| `embeddings` | Memory | Vector representations for similarity search |
| `tools_registry` | Tools | Data-driven tool definitions and policies |
| `tool_calls` | Tools | Audit log of every tool invocation |
| `workflows` | State | Request lifecycle state machine |
| `approvals` | Guardrails | Explicit approval records for risky actions |
| `sales_data` | — | Sample domain data for the demo tool |

## Core Components

- **Memory layer** — stores messages and embeddings; retrieved at the start of each turn to give the agent conversation context.
- **Tool registry** — loads callable tools from the `tools_registry` table; tools are data, not hard-coded functions.
- **Workflow tracking** — records state transitions (`started` → `awaiting_approval` → `completed`) so every request is auditable.
- **Guardrails** — create an `approvals` record and pause execution when a tool has `requires_approval = true`.
- **Agent orchestrator** — coordinates each step in `app/agent.py`; intentionally small so the architecture is visible.

## Why This Design

In many agent frameworks, memory, tool state, and workflow progress are scattered across in-memory objects, framework internals, or proprietary stores. Here everything lands in PostgreSQL so the system is:

- **Inspectable** — query any table to see exactly what the agent knows and has done.
- **Debuggable** — a failing request leaves a complete trail across `messages`, `tool_calls`, `workflows`, and `approvals`.
- **Testable** — the in-memory adapter mirrors the same interface, so tests run without a live database.
- **Extendable** — add real embeddings, LLM calls, or RLS policies without changing the core schema.
