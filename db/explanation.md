# Database Design Notes

This demo treats PostgreSQL as the central nervous system for the agent.

## Why Each Table Exists

- `conversations`: groups related turns into a stable session identifier.
- `messages`: stores the raw conversation transcript.
- `embeddings`: stores vector representations that can power similarity search with `pgvector`.
- `tools_registry`: lets the agent discover tools from data instead of hard-coded lists.
- `tool_calls`: captures execution history for observability and audit trails.
- `workflows`: records lifecycle state for every request.
- `approvals`: models guardrail checkpoints explicitly.
- `sales_data`: gives the demo tool something real to query.

## Why `pgvector` Matters

The vector column keeps semantic memory in the same database as transactional state. That means a single PostgreSQL instance can support:

- recent-message retrieval
- vector similarity search
- workflow state tracking
- tool metadata
- audit logs

## Suggested Demo Queries

- `Show me the strongest sales region`
- `Summarize revenue by region`
- `Please issue a refund for order 42`

The first two should run through the sales analysis tool. The refund request should trigger the approval guardrail.
