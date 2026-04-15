# Core Concepts

This document explains the foundational ideas behind this project. Start here if you are new to AI agents, pgvector, or the patterns used in this demo.

---

## What Is an AI Agent?

A **chatbot** takes a message and returns a reply. Each turn is independent — it has no memory of what came before and cannot take actions beyond generating text.

An **AI agent** is fundamentally different. It:

- Maintains memory across turns and sessions
- Has access to tools it can invoke to take real actions
- Tracks progress across multi-step tasks
- Operates within guardrails that control what it is allowed to do

You can think of an agent as a loop:

```
observe → plan → act → observe again
```

The LLM (language model) is the reasoning engine inside this loop. But the loop itself — the memory, the tools, the state, the safety checks — lives in your infrastructure. That is what this demo is about.

---

## The 4 Pillars of a Production Agent

Every reliable agent system needs four things. This demo implements all four using PostgreSQL.

### 1. Memory — what the agent knows

Without memory, every conversation starts from zero. The agent cannot remember what the user said last turn, let alone last week.

This demo stores two kinds of memory:

- **Episodic memory** — the conversation transcript. Every message the user and agent have exchanged, stored in the `messages` table in chronological order. At the start of each turn, the agent retrieves the last few messages to give the LLM context.

- **Semantic memory** — vectorized representations of messages, stored in the `embeddings` table. In a production system, these would be used to find the most *relevant* past messages for a given query — not just the most recent ones.

### 2. Tools — what the agent can do

Tools are how the agent acts on the world. Without tools, an agent can only talk. With tools, it can query databases, send emails, issue refunds, update records, call external APIs.

In most frameworks, tools are hard-coded Python functions. This demo takes a different approach: **tools are rows in a database table** (`tools_registry`). The agent loads them at runtime. This means you can add, remove, or modify tools without changing any code.

### 3. State — what the agent is doing

When an agent executes a multi-step task, something needs to track where it is in the process. If the process crashes or the session times out, you need to know what was completed and where to resume.

This demo stores workflow state in the `workflows` table. Every request gets a workflow record. The status (`started` → `completed` or `awaiting_approval`) is updated at each step. This is the same pattern relational databases use for transaction logs — applied to agent orchestration.

### 4. Guardrails — what the agent is allowed to do

Agents can take wrong actions. They can misinterpret a request and call a destructive tool. They can be manipulated by adversarial inputs. Guardrails are the mechanism that prevents unsafe execution.

This demo models guardrails as explicit records in the `approvals` table. When a tool is marked `requires_approval = true`, the agent creates a pending approval record and stops. A human must review and approve before execution continues. The constraint lives in the data model — it cannot be bypassed by the agent.

---

## What Is PostgreSQL's Role Here?

PostgreSQL is the **system of record** for the entire agent. Every important artifact is stored in a table:

| What the agent knows / does | Table |
|---|---|
| Conversation history | `messages` |
| Vector memory | `embeddings` |
| Available tools | `tools_registry` |
| Tool invocation history | `tool_calls` |
| Request lifecycle state | `workflows` |
| Safety decisions | `approvals` |
| Business data | `sales_data` |

This means you can understand everything the agent knows and has done by running SQL queries. No separate observability system. No opaque framework internals. Just tables.

---

## What Is pgvector?

`pgvector` is a PostgreSQL extension that adds a `VECTOR` column type and similarity search operators. It lets you store numerical vector representations of text (called **embeddings**) alongside your regular relational data.

This is important because language models don't understand text as strings — they understand it as points in a high-dimensional mathematical space. Two pieces of text that mean similar things will have vectors that are close together. `pgvector` lets you find the closest vectors with a SQL query.

### Example

```sql
-- Find the 3 messages most semantically similar to a query vector
SELECT content
FROM embeddings
JOIN messages ON messages.id = embeddings.message_id
ORDER BY embedding <=> '[0.3, 0.5, 0.2]'::vector
LIMIT 3;
```

The `<=>` operator is the **cosine distance** operator from pgvector. Smaller values mean more similar.

---

## What Are Embeddings?

An **embedding** is a list of numbers that represents the meaning of a piece of text.

For example, the sentence "revenue is up this quarter" might be represented as a vector like `[0.82, 0.14, 0.67, ...]` with hundreds or thousands of dimensions. The sentence "sales are growing" would have a very similar vector, because it means roughly the same thing.

An embedding model (like OpenAI's `text-embedding-3-small`) converts text into these vectors. Once text is stored as vectors, you can find semantically related content using mathematical distance — even if the exact words don't match.

### Why this matters for agents

When an agent needs to retrieve relevant memory, it should not just return the most recent messages. It should return the messages that are most *relevant to the current query*. Embeddings enable this.

In this demo, embeddings are simplified to 3 dimensions using a formula for clarity. In production, you would use a real embedding model and 768 or 1536 dimensions. See [docs/extensions.md](extensions.md) for how to upgrade.

---

## What Is the Repository Pattern?

The `db.py` file contains two classes that implement the same interface:

- `InMemoryRepository` — stores everything in Python dictionaries. Used by tests and as the fallback when no database is configured.
- `PostgresRepository` — stores everything in a real PostgreSQL database using `psycopg3`.

Both classes implement identical methods (`store_message`, `load_tools`, `create_workflow`, etc.). The agent code never knows which one it is using. This is called the **repository pattern** — it separates the business logic from the storage implementation.

This design makes the demo:
- **Testable** without a database
- **Runnable** on any laptop without setup
- **Upgradeable** — swap the repository without changing agent logic

---

## Why Not Just Use a Vector Database?

Purpose-built vector databases (Pinecone, Weaviate, Chroma) are optimized for similarity search. They are good at finding similar vectors quickly. But they have a fundamental limitation: they cannot participate in transactions with your relational data.

When an agent marks a task complete AND stores a new memory, both operations should succeed or both should fail atomically. A vector database cannot be part of that transaction.

PostgreSQL with `pgvector` gives you:

- Vector similarity search via `pgvector`
- ACID transactions across all tables
- Joins between vector results and structured data in a single query
- Row-level security, audit logging, and familiar SQL tooling

The trade-off: at very large scale (hundreds of millions of vectors), a dedicated vector database may be faster. For most agent workloads, `pgvector` is more than sufficient — and you eliminate an entire service from your stack.

---

## How Does Tool Selection Work in This Demo?

When the agent receives a query, it needs to decide which tool to use. In production, this would be done by computing the embedding of the query and finding the tool whose description embedding is most similar.

In this demo, it uses **keyword matching** for simplicity. Each tool in `tools_registry` has a `keyword_hint` field — a comma-separated list of keywords. The agent counts how many of those keywords appear in the user's query and picks the tool with the highest score.

Example:
- Query: "Show me the strongest sales region"
- `run_sales_analysis` keywords: `sales, revenue, region, analysis, trend` → 2 matches (`sales`, `region`)
- `issue_refund` keywords: `refund, credit, return` → 0 matches
- Winner: `run_sales_analysis`

This is deterministic and transparent — easy to understand and debug during a live demo.

---

## Where Should I Start Reading the Code?

Recommended reading order:

1. `db/schema.sql` — understand what tables exist and why
2. `db/seed.sql` — see the demo data
3. `app/memory.py` — the simplest module (2 functions)
4. `app/tools.py` — tool loading and keyword selection
5. `app/workflow.py` — workflow creation and state updates
6. `app/agent.py` — the orchestration loop that ties it all together
7. `app/db.py` — the two repository implementations

For a guided walkthrough with explanations at each step, see [docs/reading_the_code.md](reading_the_code.md).
