# Extension Ideas

This repository is intentionally small, but it is ready for several upgrades.

## About the Current Embeddings

The demo uses a deterministic 3-dimension formula to generate embeddings:

```python
embedding = [len(content) / 10, 0.5, len(role) / 10]
```

This keeps setup completely dependency-free — no API keys, no model downloads, no network calls. The values are predictable and easy to reason about during a live demo.

The trade-off is that these embeddings carry no real semantic meaning. Similarity search will return results based on message length rather than conceptual relevance.

### Replacing with real embeddings

**Step 1 — Update the schema column dimension**

Change `VECTOR(3)` in `db/schema.sql` to match your chosen model:

```sql
-- OpenAI text-embedding-3-small
embedding VECTOR(1536)

-- Most open-source models (e.g. nomic-embed-text)
embedding VECTOR(768)
```

**Step 2 — Replace `_make_embedding()` in `app/agent.py`**

Option A — OpenAI SDK:
```python
import openai

def _make_embedding(text: str) -> list[float]:
    response = openai.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding
```

Option B — `pgai` extension (embedding runs inside PostgreSQL, no round-trip):
```sql
SELECT ai.embed('text-embedding-3-small', content) FROM messages WHERE id = $1;
```

**Step 3 — Add an HNSW index for fast similarity search**

```sql
CREATE INDEX ON embeddings USING hnsw (embedding vector_cosine_ops);
```

**Step 4 — Switch from keyword tool selection to vector similarity**

Add a `description_embedding VECTOR(1536)` column to `tools_registry`, generate embeddings for each tool description, then replace keyword matching in `app/tools.py` with:

```sql
SELECT name, description, tool_type, keyword_hint, requires_approval, sql_template
FROM tools_registry
ORDER BY description_embedding <=> $query_embedding
LIMIT 3;
```

---

## Other Possible Next Steps

- Add cosine similarity search with `pgvector` HNSW indexes.
- Add richer tool routing using confidence scores.
- Add approval decisions and workflow resumption logic.
- Add multiple domain tables beyond sales analytics.
- Add an LLM call for natural-language answer generation.

For a full list of what would be needed for a production deployment, see [docs/production_considerations.md](production_considerations.md).
