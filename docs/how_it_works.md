# How It Works

This document traces the complete lifecycle of a single agent request from the moment a query arrives to the moment a response is returned. Every step maps to specific code and a specific database operation.

---

## The Entry Point

When you run:

```bash
python app/main.py --query "Show me the strongest sales region"
```

The `main()` function in `app/main.py`:
1. Calls `build_repository()` to get either `PostgresRepository` or `InMemoryRepository`
2. Prints a banner showing which mode is active
3. Creates an `Agent` instance
4. Calls `agent.handle_query(user_id, query)`
5. Pretty-prints the result

Everything interesting happens inside `handle_query()`.

---

## Step-by-Step: Inside `handle_query()`

### Step 1 — Create or reuse a conversation

```python
if conversation_id is None:
    conversation_id = self.repository.create_conversation(user_id, "Ad hoc agent session")
```

**Database operation:** `INSERT INTO conversations (user_id, title) VALUES (...) RETURNING id`

A conversation is the top-level container for a session. Every message, workflow record, and embedding will reference this ID via foreign keys. If you pass an existing `conversation_id`, the agent continues that conversation — useful for multi-turn interactions.

---

### Step 2 — Open a workflow record

```python
workflow = create_workflow(self.repository, conversation_id, query)
```

**Database operation:** `INSERT INTO workflows (conversation_id, query_text, status) VALUES (..., 'started')`

The workflow record is created immediately, before anything else happens. This is important: if the process crashes at any later step, the database will have a record of the request with `status = 'started'`. A monitoring query on stuck workflows would surface it.

`query_text` stores the original user input verbatim. This means you can always reconstruct what the agent was trying to do, even if the workflow failed partway through.

---

### Step 3 — Store the user message

```python
store_message(self.repository, conversation_id, "user", query)
```

**Database operation:**
```sql
INSERT INTO messages (conversation_id, role, content) VALUES (..., 'user', $query);
INSERT INTO embeddings (message_id, embedding) VALUES (..., $vector);
```

Two writes happen here: one to `messages` for the text, one to `embeddings` for the vector. They are linked by `message_id`.

The vector is computed by `_make_embedding()` in `memory.py`. In this demo it is a simplified formula. In production it would be a call to an embedding model API. The schema accommodates either — only the value changes.

---

### Step 4 — Retrieve conversation context

```python
context = retrieve_context(self.repository, conversation_id)
```

**Database operation:**
```sql
SELECT id, conversation_id, role, content
FROM messages
WHERE conversation_id = $1
ORDER BY created_at DESC
LIMIT 5;
```

The results are reversed to chronological order before returning. This gives the agent the last 5 messages in the order they occurred — the format expected by LLM APIs.

**Why retrieve after storing?** Because step 3 stored the current user message. If we retrieved first, the context would be missing the message the agent is currently responding to. By storing first, the current message is included in the context.

---

### Step 5 — Load tools from the registry

```python
tools = load_tools(self.repository)
```

**Database operation:**
```sql
SELECT name, description, tool_type, keyword_hint, requires_approval, sql_template
FROM tools_registry
ORDER BY id;
```

All tools are loaded. The agent will select from this list in the next step. In this demo, the full table is fetched on every request. In production you would cache this since the registry changes rarely.

---

### Step 6 — Select the best tool

```python
tool = select_tool(query, tools)
```

**No database operation** — this runs in Python against the already-loaded list.

The keyword scoring algorithm counts how many keywords from each tool's `keyword_hint` appear in the query. The highest-scoring tool is selected.

If no tool matches, the agent returns a "no tool found" response and marks the workflow `completed`. It does not crash.

---

### Step 7 — Check for approval requirement

```python
if tool["requires_approval"]:
    approval = self.repository.create_approval(workflow["id"], tool["name"], "...")
    workflow = update_workflow(..., "awaiting_approval", response)
    return {...}
```

**Database operations:**
```sql
INSERT INTO approvals (workflow_id, tool_name, status, reason)
VALUES (..., 'pending', $reason);

UPDATE workflows SET status = 'awaiting_approval', last_message = $response
WHERE id = $workflow_id;
```

If the tool requires approval, the function returns early. Tool execution is skipped entirely. The workflow is left in `awaiting_approval` state and the approval record is left in `pending` state.

The constraint is structural: the code path that calls `execute_tool()` is simply never reached. There is no way for a model-generated decision to bypass this check.

---

### Step 8 — Execute the tool

```python
tool_result = self.repository.execute_tool(tool, query)
```

**Database operation (PostgresRepository):**
```sql
-- Runs tool["sql_template"] directly:
SELECT region, SUM(revenue) AS total_revenue
FROM sales_data
GROUP BY region
ORDER BY total_revenue DESC;
```

The `execute_tool()` method runs the `sql_template` stored in the tool record. The result is a dictionary with `rows` (the full result set) and `summary` (a human-readable string extracted from the first row).

For the in-memory repository, this is computed in Python from `self.sales_data`.

---

### Step 9 — Log the tool call

```python
self.repository.log_tool_call(
    workflow["id"], tool["name"],
    {"query": query, "conversation_id": conversation_id},
    tool_result
)
```

**Database operation:**
```sql
INSERT INTO tool_calls (workflow_id, tool_name, input_payload, output_payload)
VALUES (..., $tool_name, $input::jsonb, $output::jsonb);
```

Every invocation is logged — what was called, what was passed in, what came back. This is your audit trail. You can answer "what did the agent do on Tuesday at 3pm?" with a SQL query against this table.

---

### Step 10 — Compose and store the response

```python
response = self._compose_response(context, tool, tool_result)
store_message(self.repository, conversation_id, "assistant", response)
workflow = update_workflow(self.repository, workflow["id"], "completed", response)
```

**Database operations:**
```sql
-- Store the assistant response:
INSERT INTO messages (conversation_id, role, content) VALUES (..., 'assistant', $response);
INSERT INTO embeddings (message_id, embedding) VALUES (..., $vector);

-- Close the workflow:
UPDATE workflows SET status = 'completed', last_message = $response WHERE id = $workflow_id;
```

The response is composed from the tool result and the conversation context. In this demo it is a template string. In a production system, this is where you would call the LLM with the context, tool results, and any instructions to generate a natural-language response.

The response is stored as an `assistant` message (mirroring it back into the conversation transcript), and the workflow is marked `completed`.

---

## The Full Picture

Here is the complete sequence on one screen:

```
handle_query("demo-user", "Show me the strongest sales region")
    │
    ├─ INSERT conversations → id=1
    ├─ INSERT workflows (status='started') → id=1
    ├─ INSERT messages (role='user') → id=3
    ├─ INSERT embeddings → id=3
    ├─ SELECT messages (last 5) → context
    ├─ SELECT tools_registry → [run_sales_analysis, issue_refund]
    │    select_tool() → run_sales_analysis (score=2)
    │    requires_approval? → false → continue
    ├─ SELECT sales_data (tool execution) → ranked regions
    ├─ INSERT tool_calls → id=1
    ├─ INSERT messages (role='assistant') → id=4
    ├─ INSERT embeddings → id=4
    └─ UPDATE workflows (status='completed') → done
```

Every arrow in that diagram is a database operation. Every operation is recoverable, auditable, and queryable.

---

## What Happens With the Refund Query

```bash
python app/main.py --query "Please refund the customer"
```

The flow is identical through step 6. At step 7, `issue_refund` has `requires_approval = true`, so the path diverges:

```
    ├─ INSERT workflows (status='started') → id=2
    ├─ INSERT messages (role='user') → id=5
    ├─ SELECT tools_registry → [run_sales_analysis, issue_refund]
    │    select_tool() → issue_refund (keyword: 'refund')
    │    requires_approval? → true → STOP
    ├─ INSERT approvals (status='pending') → id=1
    ├─ INSERT messages (role='assistant', content='Approval required...') → id=6
    └─ UPDATE workflows (status='awaiting_approval') → done
         (execute_tool is never called)
```

The refund never executes. The approval record sits in `pending` state waiting for a human decision.
