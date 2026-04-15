# Workflow State Architecture

## Why State Matters for Agents

A simple question-and-answer chatbot is stateless: each request is independent and complete in itself. An agent is different. It may:

- Execute a task that spans multiple steps
- Wait for human approval before continuing
- Need to resume after a process crash or timeout
- Be inspected mid-execution by an operator

All of this requires **persistent state**. If the workflow's progress lives only in memory, any interruption means starting over. By persisting state in PostgreSQL, the agent's execution becomes recoverable, auditable, and inspectable.

---

## The Workflow Record

Every call to `agent.handle_query()` creates one row in the `workflows` table:

```sql
INSERT INTO workflows (conversation_id, query_text, status)
VALUES ($conversation_id, $query_text, 'started')
RETURNING id, conversation_id, query_text, status, last_message;
```

| Column | What it captures |
|---|---|
| `conversation_id` | Links this request to its conversation context |
| `query_text` | The original user input — preserved so you can always answer "what was the agent trying to do?" |
| `status` | Current state in the lifecycle |
| `last_message` | The most recent response or status message |
| `created_at` | When the request arrived |
| `updated_at` | When the state last changed |

---

## The State Machine

The workflow moves through states as the agent processes the request:

```
         ┌─────────┐
         │ started │   ← created when request arrives
         └────┬────┘
              │
      ┌───────┴────────┐
      │                │
      ▼                ▼
┌──────────┐   ┌──────────────────┐
│completed │   │awaiting_approval │   ← tool requires human review
└──────────┘   └──────────────────┘
```

### `started`
Set when `create_workflow()` is called at the beginning of `handle_query()`. The agent is processing — memory is being retrieved, tools are being selected.

If the system crashes at this state, the workflow row is left with `status = 'started'`. A monitoring query can surface these:

```sql
SELECT * FROM workflows
WHERE status = 'started'
  AND created_at < NOW() - INTERVAL '5 minutes';
```

Rows stuck in `started` for too long are a sign of a hung or crashed process.

### `awaiting_approval`
Set when the selected tool has `requires_approval = true`. The agent pauses here. The workflow stays in this state until a human reviews the corresponding `approvals` record and updates its status.

In production, you would build a simple admin interface that:
1. Queries `approvals WHERE status = 'pending'`
2. Displays the tool name and reason for review
3. Allows the reviewer to `UPDATE approvals SET status = 'approved', decided_at = NOW()`
4. Triggers the agent to resume and execute the tool

### `completed`
Set when the agent finishes processing — whether the tool ran successfully, no tool was found, or the workflow was blocked by a guardrail and the agent responded with an explanation. `completed` means "this workflow is done, no further action needed."

---

## Why Not Use a Separate Workflow Engine?

Dedicated workflow engines (Temporal, Airflow, Prefect) are powerful tools. They are also additional systems to deploy, monitor, and maintain.

For most agent workloads, PostgreSQL is sufficient as a workflow store:

- `SELECT FOR UPDATE SKIP LOCKED` enables a distributed task queue
- Atomic status transitions prevent two workers from claiming the same workflow
- The same database that stores agent state also stores the workflow state — no data sync required
- Every DBA already knows how to query and monitor PostgreSQL tables

The `workflows` table in this demo is the foundation for all of these patterns. The state machine is simple by design — it is enough to teach the concept without the complexity of a full workflow engine.

---

## State Transitions in Code

The state machine lives in `app/agent.py`. The transitions are explicit and easy to follow:

**Transition 1 — Normal completion:**
```python
workflow = create_workflow(repository, conversation_id, query)   # started
# ... tool runs ...
workflow = update_workflow(repository, workflow["id"], "completed", response)
```

**Transition 2 — Approval required:**
```python
workflow = create_workflow(repository, conversation_id, query)   # started
# ... tool requires approval ...
workflow = update_workflow(repository, workflow["id"], "awaiting_approval", response)
```

**Transition 3 — No tool found:**
```python
workflow = create_workflow(repository, conversation_id, query)   # started
# ... no tool matched ...
workflow = update_workflow(repository, workflow["id"], "completed", "no tool found")
```

Every path through the code ends in an explicit status update. There is no ambiguous terminal state.

---

## Extending the State Machine

The three states in this demo are enough for teaching. A production agent might add:

| Status | When used |
|---|---|
| `retrying` | Tool failed; agent is retrying with backoff |
| `failed` | Exceeded retry limit; requires operator intervention |
| `cancelled` | User or operator cancelled the workflow |
| `paused` | Agent waiting for an external event (timer, webhook) |

These additions do not require schema changes — they are just new values for the `status` column. Add a `CHECK` constraint to enforce the valid set:

```sql
ALTER TABLE workflows
ADD CONSTRAINT workflows_status_check
CHECK (status IN ('started', 'awaiting_approval', 'completed', 'retrying', 'failed', 'cancelled', 'paused'));
```

---

## Observability Through State

Because every workflow is a row, you can build dashboards and alerts with plain SQL:

```sql
-- How many workflows are currently stuck awaiting approval?
SELECT COUNT(*) FROM workflows WHERE status = 'awaiting_approval';

-- What is the completion rate in the last hour?
SELECT
    status,
    COUNT(*) AS count
FROM workflows
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY status;

-- Which queries most often result in no tool being found?
SELECT query_text, COUNT(*) AS occurrences
FROM workflows
WHERE last_message LIKE '%could not find a matching tool%'
GROUP BY query_text
ORDER BY occurrences DESC;
```

This kind of observability is built-in. No separate monitoring system needed.
