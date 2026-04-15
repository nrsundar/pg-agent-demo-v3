# Guardrails Architecture

## Why Agents Need Guardrails

Agents are powerful precisely because they can take actions — querying databases, issuing refunds, sending notifications, modifying records. That same power makes them dangerous without constraints.

Without guardrails, an agent might:
- Execute a destructive action based on a misunderstood request
- Be manipulated by a carefully crafted user input (prompt injection)
- Take a real-money action (payment, refund) without human review
- Perform an irreversible operation during a period when it should be paused

Guardrails are the mechanism that bounds what the agent is allowed to do. In this demo, guardrails are modeled as explicit database records — not framework callbacks, not in-memory flags.

---

## The Approval Model

Every tool in `tools_registry` has a `requires_approval` boolean:

```sql
requires_approval BOOLEAN NOT NULL DEFAULT FALSE
```

When this is `true`, the agent does not execute the tool. The execution path in `agent.py` checks this flag before calling `execute_tool()`:

```python
if tool["requires_approval"]:
    approval = self.repository.create_approval(
        workflow["id"],
        tool["name"],
        "Tool flagged as approval-required by policy.",
    )
    workflow = update_workflow(..., "awaiting_approval", response)
    return {..., "approval": approval}

# Only reached if requires_approval is False:
tool_result = self.repository.execute_tool(tool, query)
```

The code path that executes the tool is simply never reached when approval is required. The guardrail is structural, not advisory.

---

## The `approvals` Table

When an approval is required, a record is created:

```sql
INSERT INTO approvals (workflow_id, tool_name, status, reason)
VALUES ($workflow_id, $tool_name, 'pending', $reason)
RETURNING id, workflow_id, tool_name, status, reason;
```

The `status` column has a `CHECK` constraint:

```sql
status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected'))
```

This constraint means the database itself enforces the valid states. Even if a bug in application code tries to set `status = 'maybe'`, the database will reject the insert or update with an error. The guardrail cannot be silently bypassed by a code mistake.

---

## The Approval Lifecycle

```
Tool invoked with requires_approval = true
            │
            ▼
  approvals row created
  status = 'pending'
  decided_at = NULL
            │
            ▼
  Workflow paused at
  status = 'awaiting_approval'
            │
            ▼
  Human reviewer queries:
  SELECT * FROM approvals WHERE status = 'pending';
            │
      ┌─────┴─────┐
      ▼           ▼
  Approved     Rejected
      │           │
      ▼           ▼
  UPDATE approvals   UPDATE approvals
  SET status =       SET status =
  'approved',        'rejected',
  decided_at = NOW() decided_at = NOW()
      │
      ▼
  Agent resumes
  (in a production system)
```

In this demo, the workflow stays in `awaiting_approval` permanently — there is no resume mechanism. This is intentional: the demo shows the guardrail triggering and the approval record being created. Resumption is the natural extension described in [docs/extensions.md](../docs/extensions.md).

---

## What `decided_at` Tells You

The `decided_at` column is `NULL` until a decision is made:

```sql
decided_at TIMESTAMPTZ NULL
```

This design lets you answer operational questions quickly:

```sql
-- How many approvals are still waiting for a decision?
SELECT COUNT(*) FROM approvals WHERE decided_at IS NULL;

-- What is the average time to decision?
SELECT AVG(decided_at - created_at) FROM approvals WHERE decided_at IS NOT NULL;

-- Which tools are most frequently flagged for approval?
SELECT tool_name, COUNT(*) AS requests
FROM approvals
GROUP BY tool_name
ORDER BY requests DESC;
```

---

## Why Database Records Beat In-Memory Flags

Many agent frameworks implement guardrails as middleware callbacks or in-memory configuration. This works but has problems:

| Approach | Visibility | Auditability | Survivability |
|---|---|---|---|
| In-memory flag | Low — only visible in code | None — no log | None — lost on restart |
| Config file | Medium — visible if you read the file | Limited | Survives restart |
| Database record | High — queryable, visible to all | Full | Survives crash |

The database approach means:
- Every guardrail trigger is a durable, queryable event
- Security audits can review exactly what was blocked and why
- The approval queue survives process crashes and restarts
- Multiple services can share the same approval state

---

## Extending the Guardrail System

The `requires_approval` flag is the simplest possible guardrail. In production you would extend it with:

### Risk levels
Add a `risk_level INTEGER` column to `tools_registry` (e.g., 1 = read-only, 5 = destructive). Route high-risk tools to a more rigorous approval queue.

### Policy tables
Replace the boolean flag with a join to a `tool_policies` table that contains rules like:
- "Tools of type `payment` always require approval"
- "Users with role `admin` can bypass approval for `risk_level <= 3`"
- "No destructive operations after business hours"

### Row-level security
Use PostgreSQL's `SET LOCAL app.user_id = $user_id` combined with RLS policies to ensure the agent can only see and modify rows belonging to the current user — regardless of what SQL it generates. This is a guardrail at the database level that the application layer cannot override.

### Audit triggers
Add a PostgreSQL trigger on sensitive tables that writes to an append-only `agent_audit_log` table. Even if the application fails to call `log_tool_call()`, the database captures the event.
