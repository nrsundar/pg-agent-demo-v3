# Mock Embeddings

## Why This Demo Uses Mock Embeddings

This demo uses a deterministic 3-dimension formula to generate embeddings instead of calling a real embedding model:

```python
embedding = [
    round(min(len(content), 10) / 10, 2),  # content length signal
    0.5,                                     # constant
    round(len(role) / 10, 2)                 # role length signal
]
```

There are three reasons for this deliberate choice:

### 1. No API keys required
A real embedding model (OpenAI, Cohere, pgai) requires an API key and a network call. This demo is designed to run on any laptop, in any conference room, with or without internet access. Removing the external dependency makes it reliable.

### 2. Deterministic and testable
The mock formula always produces the same vector for the same input. This makes tests predictable and makes it easy to reason about what the agent is doing during a live demo. You can print the vectors on screen and explain exactly what they mean.

### 3. Schema is production-ready
The `embeddings` table uses the standard `VECTOR` column type from `pgvector`. The structure, indexes, and retrieval patterns are identical to what you would use with real embeddings. Only the values change.

---

## What This Means for the Demo

The 3-dimension vectors carry no real semantic meaning. Two messages with the same word count get similar vectors even if they mean completely different things. This means:

- Similarity search returns results based on text length, not meaning
- The `query_sheet.sql` hybrid retrieval example uses a hardcoded vector `[0.3, 0.5, 0.2]`
- The demo shows the **structure** of semantic memory, not true semantic retrieval

This is an intentional trade-off for a teaching demo. The audience sees how the system is wired together. The upgrade to real embeddings is additive — it does not change the schema or the retrieval pattern.

---

## How to Replace with Real Embeddings

### Step 1 — Update the schema

Change `VECTOR(3)` in `db/schema.sql` to match your chosen model:

```sql
-- OpenAI text-embedding-3-small
embedding VECTOR(1536)

-- Most open-source models (e.g. nomic-embed-text)
embedding VECTOR(768)
```

### Step 2 — Replace the embedding function in `app/memory.py`

**Option A — OpenAI:**
```python
import openai

def _make_embedding(text: str) -> list[float]:
    response = openai.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding
```

**Option B — pgai (embedding runs inside PostgreSQL, no round-trip):**
```sql
SELECT ai.embed('text-embedding-3-small', content)
FROM messages WHERE id = $1;
```

### Step 3 — Add an HNSW index for fast similarity search

```sql
CREATE INDEX ON embeddings USING hnsw (embedding vector_cosine_ops);
```

### Step 4 — Update retrieval to use real similarity

```sql
SELECT m.content, e.embedding <=> $query_vector AS distance
FROM embeddings e
JOIN messages m ON m.id = e.message_id
WHERE m.conversation_id = $conversation_id
ORDER BY distance
LIMIT 5;
```

Once these four steps are complete, the agent has genuine semantic memory — it retrieves the most relevant past messages for any query, not just the most recent ones.

---

## Talking Point for the Conference

> *"We use a mock embedding formula so this demo runs without an API key or internet connection. The `embeddings` table, the `VECTOR` column, and the similarity search query are all production-ready. Swap the formula for a real embedding model and semantic retrieval works immediately — nothing else changes."*
