# Memory Architecture

## Why Agents Need Memory

A language model, by itself, is stateless. Every time you call it, it starts fresh. It has no knowledge of what you asked five minutes ago, what tools it invoked yesterday, or what facts it learned last week.

For an agent to be useful across sessions, it needs an external memory system. PostgreSQL serves as that system in this demo.

---

## Two Layers of Memory

### Layer 1: Episodic Memory — the conversation transcript

**What it is:** A chronological record of every message exchanged in a session.

**Why it matters:** When the LLM generates a response, it needs context from earlier in the conversation. Without it, the agent cannot answer follow-up questions, cannot refer back to earlier facts, and appears to "forget" what was just said.

**How it is stored:** The `messages` table holds every turn, tagged with a `role`:

| Role | Meaning |
|---|---|
| `user` | A message from the human |
| `assistant` | A response from the agent |
| `system` | A system prompt or instruction |
| `tool` | Output from a tool invocation |

These role names deliberately match the standard LLM API message format used across providers. When you integrate a real LLM, you can pass the rows from this table directly to the API with minimal transformation.

**How retrieval works:** At the start of each turn, `retrieve_context()` fetches the last 5 messages for the conversation:

```sql
SELECT id, conversation_id, role, content
FROM messages
WHERE conversation_id = $1
ORDER BY created_at DESC
LIMIT 5;
```

The results are reversed before returning so the messages are in chronological order (oldest first), which is the format LLM APIs expect.

**Tuning the window:** The `limit=5` default is conservative. In production you would tune this based on:
- Your LLM's context window size (e.g., 128k tokens for large models)
- The cost of tokens (larger context = higher cost per call)
- The nature of your tasks (long research tasks need more history than quick lookups)

For very long conversations, you might summarize older turns and inject the summary as a `system` message instead of including every message verbatim.

---

### Layer 2: Semantic Memory — vector representations

**What it is:** Numerical representations (embeddings) of messages that enable similarity-based retrieval.

**Why it matters:** Episodic memory retrieves the most *recent* messages. Semantic memory retrieves the most *relevant* messages for the current query — regardless of when they occurred.

Consider a user who mentioned their preferred currency three sessions ago. Episodic retrieval would miss it. Semantic retrieval would find it because the new query is conceptually related.

**How it is stored:** The `embeddings` table holds a `VECTOR` column alongside a foreign key to `messages`:

```sql
CREATE TABLE embeddings (
    id         BIGSERIAL PRIMARY KEY,
    message_id BIGINT REFERENCES messages(id),
    embedding  VECTOR(3) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**The demo's embeddings:** This demo uses a simplified 3-dimension formula:

```python
embedding = [
    round(min(len(content), 10) / 10, 2),  # content length signal
    0.5,                                     # constant
    round(len(role) / 10, 2)                 # role length signal
]
```

These vectors carry no real semantic meaning — they are used to demonstrate the storage and retrieval structure without requiring an embedding model. The schema is production-ready; only the generation step needs to change.

**Similarity search with pgvector:** Once real embeddings are in place, you can retrieve semantically relevant messages with:

```sql
SELECT m.content, e.embedding <=> $query_vector AS distance
FROM embeddings e
JOIN messages m ON m.id = e.message_id
WHERE m.conversation_id = $conversation_id
ORDER BY distance
LIMIT 5;
```

The `<=>` operator is cosine distance. Smaller values = more similar. The `HNSW` index (Hierarchical Navigable Small World) makes this fast even with millions of vectors:

```sql
CREATE INDEX ON embeddings USING hnsw (embedding vector_cosine_ops);
```

---

## Why Both Layers Together

Episodic and semantic memory serve different retrieval patterns:

| Pattern | Use episodic | Use semantic |
|---|---|---|
| "What did the user say just now?" | Yes | No |
| "What happened in this session?" | Yes | No |
| "Has the user mentioned X before?" | Possibly | Yes |
| "Find context related to this topic" | No | Yes |
| "What tools worked for similar queries?" | No | Yes |

A production agent uses both — episodic for immediate context, semantic for long-range retrieval. This demo has the structure for both; the semantic layer becomes fully functional once a real embedding model is plugged in.

---

## Why PostgreSQL for Memory?

Many purpose-built vector databases exist (Pinecone, Weaviate, Chroma). The key advantage of keeping memory in PostgreSQL is that memory stays co-located with transactional state.

When an agent writes a memory AND updates a workflow status, both can be part of the same transaction. If one fails, both roll back. This is impossible when memory lives in a separate system.

Additionally, you can combine vector search with relational filters in a single query:

```sql
-- Find semantically similar memories, but only from the last 30 days
-- and only for this specific user
SELECT m.content, e.embedding <=> $query_vector AS distance
FROM embeddings e
JOIN messages m ON m.id = e.message_id
JOIN conversations c ON c.id = m.conversation_id
WHERE c.user_id = $user_id
  AND m.created_at > NOW() - INTERVAL '30 days'
ORDER BY distance
LIMIT 5;
```

This kind of hybrid query — vector similarity combined with relational filters — is awkward or impossible in a dedicated vector database. In PostgreSQL it is a single, indexed query.
