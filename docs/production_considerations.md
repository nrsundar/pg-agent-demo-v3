# Production Considerations

This demo is intentionally compact so every component is visible and teachable. The design maps directly to production patterns, but several pieces have been simplified or omitted to keep the focus on architecture rather than operational detail.

## What Is Simplified in This Demo

### Embeddings
The demo uses a deterministic 3-dimension formula (`[len(content)/10, 0.5, len(role)/10]`) instead of real embeddings. This keeps setup dependency-free and makes the vector values easy to reason about in a teaching context.

**In production:** Replace `_make_embedding()` in `app/agent.py` with calls to a real embedding model:
- OpenAI `text-embedding-3-small` → 1536 dimensions
- Cohere `embed-v3` → 1024 dimensions
- `pgai` extension (runs embedding inside PostgreSQL) → avoids the network round-trip entirely

Update the schema column from `VECTOR(3)` to match the chosen model's dimensions.

### Tool Selection
The demo selects tools via keyword matching against `tools_registry.keyword_hint`. This is deterministic and easy to trace.

**In production:** Replace with vector similarity search against a `description_embedding` column on `tools_registry`. Add the column, generate embeddings for each tool description, and use `ORDER BY description_embedding <=> $query_embedding LIMIT 3` to retrieve the most contextually relevant tools.

### LLM Integration
The demo generates templated responses without calling a language model. This removes the need for API keys and makes behavior predictable during a live demo.

**In production:** After tool execution, pass the tool result and conversation context to an LLM to generate a natural-language response. The PostgreSQL layer remains unchanged — only the response generation step changes.

### Row-Level Security
The demo uses no RLS policies. Any connection can read any row.

**In production:** Enable RLS on `conversations`, `messages`, `workflows`, and `approvals`. Bind each row to a `user_id` and enforce it at the database level so the agent cannot leak data across users regardless of what SQL it generates.

```sql
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY messages_isolation ON messages
    USING (conversation_id IN (
        SELECT id FROM conversations WHERE user_id = current_setting('app.user_id')
    ));
```

### Audit Logging
The `tool_calls` table provides a basic audit trail. There is no tamper-evident log or compliance-grade event stream.

**In production:** Add `pg_audit` for session-level logging. Consider an append-only `agent_events` table with an insert-only role and no `DELETE` or `UPDATE` privileges for the application user.

### Connection Pooling
The demo opens a new connection for every database call.

**In production:** Run [PgBouncer](https://www.pgbouncer.org/) in transaction mode between the application and PostgreSQL. This is especially important for agent workloads where many short-lived LLM calls each trigger small database operations.

### Asynchronous Execution
The demo uses synchronous `psycopg` calls, which block while waiting for the database.

**In production:** Switch to `psycopg` async adapters (`await conn.execute(...)`) or `asyncpg`. This allows the orchestration loop to handle multiple agent requests concurrently without thread-per-request overhead.

### Distributed Task Queue
The demo runs a single-process orchestration loop.

**In production:** Use `SELECT FOR UPDATE SKIP LOCKED` to build a PostgreSQL-native task queue. Multiple agent worker processes can poll the `workflows` table for `status = 'started'` work without conflict, with no Redis or Kafka required for moderate throughput.

```sql
SELECT id, query_text
FROM workflows
WHERE status = 'started'
ORDER BY created_at
LIMIT 1
FOR UPDATE SKIP LOCKED;
```

### Workflow Retry and Recovery
The demo does not implement retry logic or checkpoint recovery.

**In production:** Add an `attempts` counter and `scheduled_at` timestamp to `workflows`. On failure, increment `attempts` and set `scheduled_at = NOW() + (2 ^ attempts) * INTERVAL '1 second'` for exponential backoff. A separate reaper process moves stuck workflows to a dead-letter status after a maximum retry count.

## Summary

| Concern | Demo | Production path |
|---|---|---|
| Embeddings | Mock 3-dim formula | Real model (OpenAI, pgai) |
| Tool selection | Keyword match | Vector similarity search |
| Response generation | Templated string | LLM call |
| Data isolation | None | Row-level security |
| Audit trail | `tool_calls` table | `pg_audit` + append-only events |
| Connection handling | New conn per call | PgBouncer |
| Concurrency | Single process | `FOR UPDATE SKIP LOCKED` workers |
| Fault tolerance | None | Retry counters, dead-letter queue |

The schema and architecture patterns shown in this demo are the right foundation. Each row in the table above is an additive improvement, not a redesign.
