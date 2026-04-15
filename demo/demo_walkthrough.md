# Demo Walkthrough

This walkthrough is designed for a live conference demo. Each step includes the command to run and the expected terminal output so you have a reference sheet during the presentation.

---

## Step 1 — Show the schema

Open `db/schema.sql` and point out that memory, tools, workflows, and guardrails all live in PostgreSQL. Key tables to highlight:

- `messages` + `embeddings` — the memory layer
- `tools_registry` — data-driven tool discovery
- `workflows` — request lifecycle state
- `approvals` — guardrail checkpoints

---

## Step 2 — Show the seed data

Open `db/seed.sql` so the audience sees:
- Two tools registered: `run_sales_analysis` (no approval) and `issue_refund` (requires approval)
- Six sales records across four regions

---

## Step 3 — Run the sales query demo

```bash
python demo/run_demo.py
```

**Expected output:**
```
=== PostgreSQL-Powered AI Agent Demo ===
Mode: In-memory repository (DATABASE_URL not set — safe fallback for demos)

Memory retrieval:
[{'content': 'How are sales trending this quarter?',
  'conversation_id': 1,
  'id': 1,
  'role': 'user'},
 {'content': 'I can review the latest sales data and summarize the strongest '
             'region.',
  'conversation_id': 1,
  'id': 2,
  'role': 'assistant'}]

Tool selection:
{'description': 'Summarize revenue by region.',
 'keyword_hint': 'sales,revenue,region,analysis,trend',
 'name': 'run_sales_analysis',
 'requires_approval': False,
 'sql_template': 'SELECT region, SUM(revenue) AS total_revenue FROM sales_data '
                 'GROUP BY region ORDER BY total_revenue DESC;',
 'tool_type': 'sql'}

Execution result:
{'rows': [{'region': 'West', 'total_revenue': 38000.0},
          {'region': 'North', 'total_revenue': 30000.0},
          {'region': 'South', 'total_revenue': 9000.0},
          {'region': 'East', 'total_revenue': 8000.0}],
 'summary': 'Top region is West with revenue 38000.00.'}

Workflow state:
{'id': 1,
 'conversation_id': 1,
 'query_text': 'Show me the strongest sales region this quarter',
 'status': 'completed',
 'last_message': 'Top region is West with revenue 38000.00.'}

Final response:
Top region is West with revenue 38000.00.
```

**What to explain at this step:**
- Memory retrieval pulled the last 2 messages from the seeded conversation.
- Tool selection matched on keywords (`sales`, `region`) from the tool registry table.
- Execution ran the `sql_template` stored in the database.
- Workflow status moved from `started` → `completed`.
- The entire flow is driven by data in PostgreSQL, not hard-coded logic.

---

## Step 4 — Run the approval guardrail demo

```bash
python app/main.py --query "Please refund the customer"
```

**Expected output:**
```
[pg-agent] Running with InMemoryRepository (DATABASE_URL not set — demo/fallback mode)

{'context': [...],
 'response': 'Action requires approval before execution.',
 'selected_tool': {'name': 'issue_refund',
                   'requires_approval': True, ...},
 'tool_result': None,
 'workflow': {'status': 'awaiting_approval', ...}}
```

**What to explain at this step:**
- The keyword `refund` matched the `issue_refund` tool.
- Because `requires_approval = true` in the registry, execution was blocked.
- An `approvals` record was created with `status = 'pending'`.
- Workflow status is `awaiting_approval` — not failed, not completed. It is waiting.
- In a real system, a human reviews the approval record and updates its status to resume the workflow.

---

## Step 5 — Query the tables live (PostgreSQL mode)

If running against a real database, open a second terminal and run:

```bash
psql $DATABASE_URL -f demo/query_sheet.sql
```

Or run individual queries to show the audience what was persisted:

```sql
-- What did the agent remember?
SELECT role, content FROM messages ORDER BY created_at;

-- What tools are registered?
SELECT name, requires_approval FROM tools_registry;

-- What happened to the workflow?
SELECT query_text, status FROM workflows;

-- Was the refund request blocked?
SELECT tool_name, status, reason FROM approvals;

-- Revenue by region (what the tool computed)
SELECT region, SUM(revenue) AS total FROM sales_data GROUP BY region ORDER BY total DESC;
```

**What to explain at this step:**
- Every decision the agent made is queryable right here in psql.
- No separate observability system needed.
- The same `SELECT` that you would use to debug a transaction can tell you exactly what the agent did.

---

## Step 6 — Talk about extensions

Close with `docs/extensions.md` and `docs/production_considerations.md`:
- How to replace mock embeddings with real ones
- How to add LLM calls for natural-language responses
- What would be needed for a production deployment
