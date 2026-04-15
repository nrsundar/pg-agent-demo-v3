# Reading the Code

This is a guided walkthrough of every file in the project. It is written for someone who is new to agent systems and wants to understand not just *what* the code does but *why* each decision was made.

Read this alongside the actual files — open them side by side.

---

## Start here: `db/schema.sql`

Before reading any Python, read the schema. The database design tells you everything about how the system is structured.

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

This line enables `pgvector`. Without it, the `VECTOR` column type does not exist. The `IF NOT EXISTS` guard makes it safe to run multiple times.

---

### `conversations` table

```sql
CREATE TABLE IF NOT EXISTS conversations (
    id          BIGSERIAL PRIMARY KEY,
    user_id     TEXT NOT NULL,
    title       TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

A conversation is the top-level container for a session. Every message, workflow, and embedding belongs to a conversation through foreign keys. This lets you isolate state per user session cleanly.

`user_id` is stored as plain text here. In production you would add a foreign key to a `users` table and enforce row-level security so one user's conversations are never visible to another.

---

### `messages` table

```sql
CREATE TABLE IF NOT EXISTS messages (
    id               BIGSERIAL PRIMARY KEY,
    conversation_id  BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role             TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool')),
    content          TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_created_at
    ON messages (conversation_id, created_at DESC);
```

Every turn in the conversation is a row here. The `role` column mirrors the standard LLM API message format (`user`, `assistant`, `system`, `tool`). This is intentional — when you integrate a real LLM, you can pass these rows directly to the API with minimal transformation.

The composite index `(conversation_id, created_at DESC)` optimizes the most common query: "give me the last N messages for this conversation." The `DESC` direction means PostgreSQL scans from newest to oldest and can stop early once it has enough rows.

The `ON DELETE CASCADE` means if you delete a conversation, all its messages are automatically deleted too. This makes cleanup simple.

---

### `embeddings` table

```sql
CREATE TABLE IF NOT EXISTS embeddings (
    id          BIGSERIAL PRIMARY KEY,
    message_id  BIGINT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    embedding   VECTOR(3) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Each message can have an associated vector stored here. The `VECTOR(3)` type comes from the `pgvector` extension — the `3` means 3 dimensions (the demo uses a simplified formula; production systems use 768 or 1536).

Storing embeddings in a separate table rather than a column on `messages` is a deliberate design:
- You can add embeddings to existing messages without an `ALTER TABLE`
- Not every message needs an embedding (e.g., short acknowledgements)
- The table is ready for future indexing with `CREATE INDEX ... USING hnsw`

---

### `tools_registry` table

```sql
CREATE TABLE IF NOT EXISTS tools_registry (
    id                BIGSERIAL PRIMARY KEY,
    name              TEXT NOT NULL UNIQUE,
    description       TEXT NOT NULL,
    tool_type         TEXT NOT NULL,
    keyword_hint      TEXT NOT NULL,
    requires_approval BOOLEAN NOT NULL DEFAULT FALSE,
    sql_template      TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

This table is the heart of the data-driven tool system. Every column has a purpose:

| Column | Purpose |
|---|---|
| `name` | Unique identifier used in logs and approval records |
| `description` | Human-readable description; in production this becomes the embedding source for semantic tool selection |
| `tool_type` | Category tag (e.g., `sql`, `api`, `webhook`) for routing logic |
| `keyword_hint` | Comma-separated keywords used for matching in this demo |
| `requires_approval` | If `true`, the agent stops and creates an approval record before executing |
| `sql_template` | The query this tool will run when invoked |

The `UNIQUE` constraint on `name` prevents duplicate tool registrations. This matters when the table is managed by migrations rather than manual inserts.

---

### `workflows` table

```sql
CREATE TABLE IF NOT EXISTS workflows (
    id               BIGSERIAL PRIMARY KEY,
    conversation_id  BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    query_text       TEXT NOT NULL,
    status           TEXT NOT NULL,
    last_message     TEXT NOT NULL DEFAULT '',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Every call to `agent.handle_query()` creates one workflow row. The `status` column is a state machine:

```
started → completed
started → awaiting_approval
```

`query_text` stores the original user input so you can always answer "what was the agent trying to do?" from the database alone.

`last_message` stores the most recent response, making it easy to resume a workflow or display its outcome without joining to `messages`.

`updated_at` is manually updated in code (`SET updated_at = NOW()`). In production you would add a trigger to handle this automatically.

---

### `tool_calls` table

```sql
CREATE TABLE IF NOT EXISTS tool_calls (
    id              BIGSERIAL PRIMARY KEY,
    workflow_id     BIGINT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    tool_name       TEXT NOT NULL,
    input_payload   JSONB NOT NULL,
    output_payload  JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Every tool execution is logged here. `input_payload` and `output_payload` use `JSONB` because the shape of inputs and outputs varies by tool — JSONB gives you flexibility while still being queryable.

This is your audit trail. You can answer:
- "What did the agent call and when?"
- "What data did it pass to the tool?"
- "What did the tool return?"

`JSONB` (binary JSON) in PostgreSQL supports indexing, containment queries (`@>`), and path extraction (`->>`). It is strictly better than `JSON` for stored data.

---

### `approvals` table

```sql
CREATE TABLE IF NOT EXISTS approvals (
    id           BIGSERIAL PRIMARY KEY,
    workflow_id  BIGINT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    tool_name    TEXT NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected')),
    reason       TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at   TIMESTAMPTZ NULL
);
```

The `CHECK` constraint on `status` enforces the state machine at the database level. An application bug cannot set `status = 'maybe'`. This is an example of using PostgreSQL constraints as a safety layer.

`decided_at` is `NULL` until a decision is made — a human reviewing the approvals table can immediately see which ones are still pending by filtering `WHERE decided_at IS NULL`.

---

## `db/seed.sql`

The seed file inserts two tools and six sales records. Reading it gives you a concrete picture of what the agent can do:

- `run_sales_analysis` — runs a `GROUP BY` query on `sales_data` to rank regions by revenue. `requires_approval = false`.
- `issue_refund` — a mock refund tool. `requires_approval = true`. Its `sql_template` returns a static note rather than doing anything real, which makes it safe to demonstrate.

The six sales rows cover four regions (North, South, East, West) with varying revenues, so the analysis tool has something interesting to rank.

---

## `app/memory.py`

```python
def store_message(repository, conversation_id, role, content):
    embedding = [round(min(len(content), 10) / 10, 2), 0.5, round(len(role) / 10, 2)]
    return repository.store_message(conversation_id, role, content, embedding)
```

This is the simplest module in the project — two functions.

The embedding formula `[len(content)/10, 0.5, len(role)/10]` is deliberately trivial. It produces a 3-dimension vector based on text length. It has no semantic meaning — a message saying "yes" and one saying "no" get similar vectors because they have the same length.

This is a teaching trade-off: the formula keeps the demo self-contained (no API keys, no model downloads), and the 3-dimension vectors are small enough to print on screen. The structure for real embeddings is identical — only the formula changes.

```python
def retrieve_context(repository, conversation_id, limit=5):
    return repository.get_recent_messages(conversation_id, limit=limit)
```

Context retrieval returns the last 5 messages in chronological order. This is the "short-term memory" injected into the agent's reasoning at each turn. The `limit=5` default is conservative — in production you would tune this based on your LLM's context window and the cost of tokens.

---

## `app/tools.py`

```python
def load_tools(repository):
    return repository.load_tools()
```

Tool loading is a single database read. The entire tool registry is fetched on every request in this demo. In production you would cache this, since the registry changes rarely.

```python
def select_tool(query, tools):
    normalized_query = query.lower()
    best_tool = None
    best_score = 0

    for tool in tools:
        keywords = [k.strip() for k in tool["keyword_hint"].split(",") if k.strip()]
        score = sum(1 for keyword in keywords if keyword in normalized_query)
        if score > best_score:
            best_score = score
            best_tool = tool
    ...
```

The selection algorithm scores each tool by counting keyword matches in the query. The tool with the most matches wins.

The second loop (scanning for tool name tokens) is a fallback — if no keywords matched, it checks whether any part of the tool's name appears in the query. This handles cases like typing `refund` directly when the keyword list is `refund,credit,return`.

**Why not use an LLM for tool selection?** In a production system with many tools or ambiguous queries, you would use vector similarity search (embed the query, find the closest tool description). This demo uses keywords because it is deterministic and easy to trace — you can explain exactly why a tool was chosen without calling a model.

---

## `app/workflow.py`

```python
def create_workflow(repository, conversation_id, query_text):
    return repository.create_workflow(conversation_id, query_text, status="started")

def update_workflow(repository, workflow_id, status, last_message):
    return repository.update_workflow(workflow_id, status, last_message)
```

Two functions, each one line. This module exists to give the workflow concept a named boundary in the code. Even though the functions are simple, having `workflow.py` means that if you later add retry logic, timeout handling, or event emission, there is a clear place to put it.

The initial status is always `"started"`. The transition to `"completed"` or `"awaiting_approval"` happens in `agent.py` based on the tool's `requires_approval` flag. This separation keeps the state machine explicit and visible.

---

## `app/agent.py`

This is the orchestration layer — the file that coordinates everything.

```python
class Agent:
    def __init__(self, repository):
        self.repository = repository
```

The agent is initialized with a repository. It does not know or care whether that repository is in-memory or PostgreSQL. This is the repository pattern in practice.

```python
def handle_query(self, user_id, query, conversation_id=None):
    if conversation_id is None:
        conversation_id = self.repository.create_conversation(user_id, "Ad hoc agent session")
```

If no conversation exists, create one. This allows the agent to be called with or without an existing session, making it easy to use from both the CLI and the demo script.

```python
    workflow = create_workflow(self.repository, conversation_id, query)
    store_message(self.repository, conversation_id, "user", query)
    context = retrieve_context(self.repository, conversation_id)
```

Before any tool is invoked, three things happen:
1. A workflow record is opened (status: `started`)
2. The user's message is stored in memory
3. Recent context is retrieved

Steps 2 and 3 happen in this order deliberately: store first, then retrieve. This means the message the user just sent is included in the context returned, which gives the agent a complete picture.

```python
    tools = load_tools(self.repository)
    tool = select_tool(query, tools)
    if tool is None:
        response = "I could not find a matching tool for that request."
        ...
        return {...}
```

If no tool matches, the agent responds gracefully and closes the workflow as `completed`. It does not crash. This is an important production pattern: unknown inputs should produce a safe, informative response.

```python
    if tool["requires_approval"]:
        approval = self.repository.create_approval(
            workflow["id"], tool["name"], "Tool flagged as approval-required by policy."
        )
        ...
        workflow = update_workflow(..., "awaiting_approval", response)
        return {..., "approval": approval}
```

The guardrail check is a simple boolean on the tool record. When `requires_approval` is true:
- An approval record is inserted with `status = 'pending'`
- The workflow status is updated to `awaiting_approval`
- The function returns immediately — tool execution is skipped entirely

Nothing about this relies on the agent "deciding" to check for approval. The constraint is structural: the code path that executes the tool is only reached if `requires_approval` is `false`. This is a safety-by-design approach.

```python
    tool_result = self.repository.execute_tool(tool, query)
    self.repository.log_tool_call(workflow["id"], tool["name"], {...}, tool_result)
    response = self._compose_response(context, tool, tool_result)
    store_message(self.repository, conversation_id, "assistant", response)
    workflow = update_workflow(..., "completed", response)
```

The execution path:
1. Run the tool (executes the `sql_template`)
2. Log the invocation to `tool_calls` for audit
3. Compose a response string (template-based in this demo; LLM-based in production)
4. Store the response in memory as an `assistant` message
5. Mark the workflow `completed`

Every step writes to the database. If the process crashes after step 2, you can reconstruct what happened from `tool_calls`. If it crashes after step 4, you know the response was generated but the workflow was not marked complete — a monitoring query on `workflows WHERE status = 'started'` would surface it.

---

## `app/db.py` — The Two Repositories

### `InMemoryRepository`

Uses Python dictionaries and lists for storage. It is seeded with `seed_defaults()` which populates the same data as `db/seed.sql`.

Key methods mirror the PostgreSQL ones exactly:
- `store_message()` — appends to `self.messages`, optionally to `self.embeddings`
- `load_tools()` — returns a copy of `self.tools_registry`
- `execute_tool()` — computes totals from `self.sales_data` in Python

The in-memory repository has no persistence. Data is lost when the process exits. This is intentional — it is a teaching and testing tool, not a storage system.

### `PostgresRepository`

Uses `psycopg3` (the modern Python PostgreSQL driver) with `dict_row` to return results as dictionaries rather than tuples. This means you can access columns by name (`row["region"]`) rather than by index (`row[0]`).

Each method opens a fresh connection. In production you would use a connection pool (PgBouncer or `psycopg3`'s built-in pool) to avoid the overhead of establishing a new connection per call.

```python
def execute_tool(self, tool, query):
    with self._connect() as conn, conn.cursor() as cur:
        cur.execute(tool["sql_template"])
        rows = cur.fetchall()
        ...
```

The tool's `sql_template` is executed directly. This is fine for demo purposes where the templates are controlled data in the database. In production you would add parameterization, a SQL allowlist, or a separate execution sandbox to prevent injection.

### `build_repository()`

```python
def build_repository():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return PostgresRepository(database_url)
    repository = InMemoryRepository()
    repository.seed_defaults()
    return repository
```

This factory function is the only place in the codebase that decides which implementation to use. It reads `DATABASE_URL` from the environment. If it is set, you get a real database. If not, you get a seeded in-memory instance.

This single function is why the demo works on any laptop with zero setup — the fallback is automatic.

---

## `app/main.py`

The CLI entry point. Uses `argparse` to accept `--user-id`, `--conversation-id`, and `--query`. Builds the repository, runs the agent, and pretty-prints the result.

The startup banner added in the documentation improvements makes the active mode visible immediately — important during a live demo where the audience needs to know whether they are watching a real database or the in-memory fallback.

---

## `demo/run_demo.py`

A simplified demo runner that always uses `InMemoryRepository`. It skips `argparse` and runs a fixed query so there is nothing to configure. Ideal for:
- First-time setup verification
- Conference presentations where reliability matters more than flexibility
- Showing expected output to a live audience

---

## `tests/`

Four test modules, each focused on one layer:

| File | What it tests |
|---|---|
| `test_agent_flow.py` | Full end-to-end workflow: user message → tool selection → execution → response |
| `test_memory.py` | `store_message` and `retrieve_context` in isolation |
| `test_tools.py` | Tool loading and keyword selection logic |
| `test_workflow.py` | Workflow creation and status transitions |

All tests use `InMemoryRepository` via the `conftest.py` fixture. No database required to run `pytest`.

The test coverage is intentionally narrow — each test covers one concept. This makes it easy to understand what broke when a test fails.
