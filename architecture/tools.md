# Tool Registry Architecture

## What Are Tools?

Tools are how an agent takes actions beyond generating text. Without tools, an agent can only talk. With tools, it can:

- Query a database
- Call an external API
- Send a notification
- Update a record
- Execute a calculation

In this demo, every tool is a SQL query. In a real system, tools could be HTTP calls, Python functions, webhook triggers, or any other executable action.

---

## The Conventional Approach: Hard-Coded Tools

Most agent frameworks define tools as Python functions with decorators:

```python
@tool
def run_sales_analysis(region: str) -> str:
    """Summarize revenue by region."""
    ...

@tool
def issue_refund(order_id: str) -> str:
    """Issue a refund for the given order."""
    ...
```

This works for small systems but has problems:

- Adding a new tool requires a code change and a deployment
- Changing a tool's approval policy requires a code change
- You cannot inspect or query what tools exist
- Access control is buried in code, not data

---

## The Data-Driven Approach: Tools as Rows

This demo stores every tool as a row in `tools_registry`. The agent loads tools from the database at runtime.

```sql
SELECT name, description, tool_type, keyword_hint,
       requires_approval, sql_template
FROM tools_registry
ORDER BY id;
```

The result is a list of dictionaries that the agent can reason about. No imports. No decorators. No code changes needed to add or modify a tool.

---

## Anatomy of a Tool Record

```
name              → "run_sales_analysis"
description       → "Summarize revenue by region."
tool_type         → "sql"
keyword_hint      → "sales,revenue,region,analysis,trend"
requires_approval → false
sql_template      → "SELECT region, SUM(revenue) AS total_revenue
                      FROM sales_data
                      GROUP BY region
                      ORDER BY total_revenue DESC;"
```

### `name`
The unique identifier for the tool. Used in audit logs, approval records, and error messages. The `UNIQUE` constraint in the schema prevents duplicates.

### `description`
A human-readable explanation of what the tool does. In this demo it is only used for display. In a production system, you would generate an embedding from this text and store it in an additional `description_embedding VECTOR(1536)` column. Tool selection would then use vector similarity search instead of keyword matching.

### `tool_type`
A category tag. This demo only uses `"sql"`, but you could add `"api"`, `"webhook"`, `"python"`, or any other type. The `execute_tool()` method would branch on this field to call the appropriate execution path.

### `keyword_hint`
A comma-separated list of words used for tool selection in this demo. When the agent receives a query, it counts how many of these keywords appear in the query text. The tool with the most keyword matches wins.

Example: query = `"Show me the strongest sales region"`
- `run_sales_analysis` keywords: `sales, revenue, region, analysis, trend` → 2 matches
- `issue_refund` keywords: `refund, credit, return` → 0 matches
- **Winner: `run_sales_analysis`**

In production this would be replaced by vector similarity search against `description_embedding`.

### `requires_approval`
A boolean flag. When `true`, the agent does not execute the tool. Instead it:
1. Creates a record in the `approvals` table with `status = 'pending'`
2. Updates the workflow to `awaiting_approval`
3. Returns without running the SQL

This flag is the entire guardrail mechanism for this demo. The policy is visible in data, auditable, and enforceable. You can change which tools require approval by updating a row — no code change required.

### `sql_template`
The SQL query that runs when the tool is invoked. In this demo, the template runs as-is against the database. The `run_sales_analysis` template aggregates `sales_data` and returns ranked regions. The `issue_refund` template returns a static note (it is a mock — real refunds would need parameterized inputs and a proper execution path).

---

## Tool Selection in `app/tools.py`

```python
def select_tool(query, tools):
    normalized_query = query.lower()
    best_tool = None
    best_score = 0

    for tool in tools:
        keywords = [k.strip() for k in tool["keyword_hint"].split(",")]
        score = sum(1 for keyword in keywords if keyword in normalized_query)
        if score > best_score:
            best_score = score
            best_tool = tool

    if best_tool is not None:
        return best_tool

    # Fallback: check if any token of the tool name appears in the query
    for tool in tools:
        if any(token in normalized_query for token in tool["name"].lower().split("_")):
            return tool

    return None
```

The function first tries keyword scoring. If no keywords matched at all, it falls back to name-token matching. If still nothing matches, it returns `None` and the agent responds with a "no tool found" message.

**Why two passes?** The keyword approach is the primary signal. The name-token fallback catches cases like a user typing `refund` when the keyword list is `refund,credit,return` — in this case the keyword pass would have matched, but the fallback handles typos or abbreviated queries that miss the keyword list entirely.

---

## Execution Audit: `tool_calls`

Every tool invocation — whether it succeeded or not — is logged to `tool_calls`:

```sql
INSERT INTO tool_calls (workflow_id, tool_name, input_payload, output_payload)
VALUES ($workflow_id, $tool_name, $input::jsonb, $output::jsonb);
```

This gives you a complete, queryable record of:
- What tool was called
- What input was passed (the user's query and conversation context)
- What the tool returned (the full result set and summary)
- When it was called (via `created_at`)

JSONB payloads make this flexible — different tools return different shapes of data, and all of it is stored without a schema change.

---

## The Path to Production Tool Selection

The keyword approach is deliberately simple. Here is how you would upgrade it:

**Step 1:** Add a `description_embedding VECTOR(1536)` column to `tools_registry`.

**Step 2:** When a tool is added or updated, generate an embedding from its `description` and store it.

**Step 3:** At query time, embed the user's query and find the most relevant tools:

```sql
SELECT name, description, tool_type, keyword_hint, requires_approval, sql_template
FROM tools_registry
ORDER BY description_embedding <=> $query_embedding
LIMIT 3;
```

**Step 4:** Optionally pass multiple candidate tools to the LLM and let it choose, providing an explanation of which tool to use and why.

This gives you semantic tool discovery — the agent finds the right tool even when the user's words don't match any keyword exactly.
