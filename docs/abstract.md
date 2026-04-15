# PGConf 2026 — Session Abstract

**Title:** Building Production-Grade AI Agents with PostgreSQL

**Presenters:** Sundar & Shayon

---

## Abstract

The AI landscape is shifting from chatbots to autonomous agents — systems that plan, use tools, maintain memory, and take actions. While attention focuses on language models, the real differentiator for production agents is the data layer. PostgreSQL, with its combination of relational integrity, vector search, and extensibility, is emerging as the ideal backbone for agentic AI.

This session explores architectural patterns for building production-grade AI agents with PostgreSQL at the core.

### Memory Architecture

Agents need both short-term conversation context and long-term memory. We'll cover implementing:

- **Episodic memory** — conversation history with efficient retrieval
- **Semantic memory** — knowledge retrieval via pgvector similarity search
- **Procedural memory** — learned patterns stored as retrievable examples

All in PostgreSQL with proper isolation and retrieval patterns.

### Tool and Function Registries

Agents invoke tools to take actions. We'll demonstrate:

- Storing tool definitions and parameter schemas
- Dynamic tool discovery based on context
- Execution metadata and audit trails
- Approval workflows for sensitive operations

### Model Context Protocol (MCP) Integration

MCP is becoming the standard for connecting AI assistants to external systems. We'll show how to integrate MCP servers that expose PostgreSQL capabilities:

- Schema introspection for natural language queries
- Safe, parameterized query execution
- Structured data retrieval with proper formatting

### State Management

Complex agents maintain state across multi-step tasks:

- Workflow state persistence
- Checkpoint and resume patterns
- Reliable task queues for agent orchestration
- Handling failures and retries gracefully

### Grounding and Guardrails

Agents hallucinate. We'll demonstrate:

- Grounding responses in PostgreSQL data
- Fact-checking queries before responding
- Safety guardrails preventing harmful actions
- Confidence scoring based on data availability

---

## What Attendees Will See

Live demonstrations will show a working agent system that queries databases, maintains conversation context, and takes actions — all orchestrated through PostgreSQL.

We'll discuss why PostgreSQL beats purpose-built vector databases for agent workloads:

- ACID transactions for reliable state
- Mature tooling
- The ability to join vector results with structured data in a single query

---

## Demo Repository

All code from this session is available at:
**https://github.com/nrsundar/pg-agent-demo-v2**

---

## Mapping Abstract to Demo

| Abstract promise | Demo implementation | Status |
|---|---|---|
| Episodic memory | `messages` table | ✅ |
| Semantic memory via pgvector | `embeddings` table with `VECTOR(3)` | ✅ (mock embeddings — see `docs/mock_embeddings.md`) |
| Tool definitions and schemas | `tools_registry` table | ✅ |
| Dynamic tool discovery | Keyword-based selection from DB | ✅ (production: vector similarity) |
| Execution audit trails | `tool_calls` table | ✅ |
| Approval workflows | `approvals` table + guardrail check | ✅ |
| Workflow state persistence | `workflows` table | ✅ |
| Grounding in PostgreSQL data | Tool executes SQL against `sales_data` | ✅ |
| Procedural memory | Not in this demo | 📋 Production pattern only |
| MCP integration | Not in this demo | 📋 Described conceptually |
| Retry / recovery | Not in this demo | 📋 See `docs/production_considerations.md` |
| Confidence scoring | Not in this demo | 📋 See `docs/extensions.md` |
