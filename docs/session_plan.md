# PGConf 2026 — Session Plan (50 Minutes)

## Revised Slide Order

Run the live demo **before** the architecture deep dives. The audience stays engaged because they have seen the system work before the explanation begins.

---

## Timing Breakdown

| Segment | Slides | Time | Notes |
|---|---|---|---|
| Opening + Problem | 1–4 | 8 min | Chatbots vs agents, why they fail, the real bottleneck |
| Solution + Why PostgreSQL | 5–6 | 5 min | Data layer differentiator, ACID + pgvector + extensibility |
| Architecture + 4 Pillars | 7–8 | 4 min | Overview diagram, Memory / Tools / State / Guardrails |
| **Live Demo** | 15–19 | **15 min** | Run first — show the system working before explaining it |
| Memory + Hybrid Retrieval | 10 | 4 min | Episodic vs semantic, pgvector hybrid query |
| Tools + Guardrails | 11, 13 | 5 min | Data-driven registry, approval workflow |
| Putting It All Together | 14 | 2 min | Recap + tie back to demo |
| Closing + Q&A | 20 | 7 min | Key takeaways, repo link, questions |
| **Total** | | **50 min** | Includes 5-min Q&A buffer |

---

## Slides Removed From Original Deck

| Slide | Reason for removal |
|---|---|
| Slide 9 — Memory Overview | Covered live when showing `messages` + `embeddings` tables in demo |
| Slide 12 — Stateful Orchestration | Demo shows `workflows` table live — slide is redundant |
| Slide 13 detail | Keep the slide, cut script to 1 min — demo shows guardrails better than the slide |

Removing these saves 5 minutes and brings the session to exactly 50 minutes.

---

## Live Demo Script (15 Minutes)

### Minute 1–2 — Show the schema
Open `db/schema.sql`. Point out each table and map it to a pillar:
- `messages` + `embeddings` → Memory
- `tools_registry` → Tools
- `workflows` → State
- `approvals` → Guardrails

Key line to say:
> *"Everything the agent knows and does lives in these 8 tables. Let's watch them fill up."*

### Minute 3 — Show the seed data
Open `db/seed.sql`. Show the two registered tools and six sales records.

Key line to say:
> *"Two tools: one safe, one that requires approval. Six sales records across four regions. That's all the agent has to work with."*

### Minute 4–7 — Run the sales query
```bash
python demo/run_demo.py
```
Walk through the output section by section:
- **Memory retrieval** — "The agent pulled the last 2 messages for context"
- **Tool selection** — "Keywords `sales` and `region` matched `run_sales_analysis`"
- **Execution result** — "West leads with $38,000. This came from a SQL query stored in the registry"
- **Workflow state** — "Status moved from `started` to `completed`"
- **Final response** — "This is where the LLM call would go in production"

### Minute 8–10 — Run the refund guardrail
```bash
python app/main.py --query "Please refund the customer"
```
Walk through the output:
- Tool matched: `issue_refund`
- `requires_approval = true` → execution blocked
- Approval record created with `status = pending`
- Workflow stuck at `awaiting_approval`

Key line to say:
> *"The agent didn't decide to ask for approval. The constraint is structural — the execution path is never reached. That's safety by design, not by policy."*

### Minute 11–14 — Live psql queries
Open a second terminal and run queries from `demo/query_sheet.sql`:

```sql
-- What did the agent remember?
SELECT role, content FROM messages ORDER BY created_at;

-- What tools are available?
SELECT name, requires_approval FROM tools_registry;

-- What happened to the workflows?
SELECT query_text, status FROM workflows;

-- Was the refund blocked?
SELECT tool_name, status, reason FROM approvals;

-- Revenue by region
SELECT region, SUM(revenue) AS total FROM sales_data
GROUP BY region ORDER BY total DESC;
```

Key line to say:
> *"Every decision the agent made is right here. No separate observability system. The same psql you use to debug a migration tells you exactly what the agent did and why."*

### Minute 15 — Wrap the demo
Key line to say:
> *"That's the entire system — 8 tables, ~400 lines of Python, no external services. Now let me show you why each piece is designed the way it is."*

Then move into the architecture slides.

---

## Key Talking Points (Use Throughout)

- **"Systems over models"** — the LLM is the easy part; this is the hard part
- **"Everything is queryable"** — no black boxes, no framework internals
- **"Safety by design"** — approval constraints are structural, not advisory
- **"Single system"** — memory, tools, state, and guardrails in one PostgreSQL instance
- **"Production-ready scaffold"** — swap in real embeddings and an LLM without changing the schema

---

## Conference Environment Checklist

- [ ] `DATABASE_URL` set (or confirm in-memory fallback works)
- [ ] `python demo/run_demo.py` tested and output verified
- [ ] `python app/main.py --query "Please refund the customer"` tested
- [ ] `demo/query_sheet.sql` queries tested against a live database
- [ ] Second terminal open and ready for psql queries
- [ ] Expected output printed from `demo/demo_walkthrough.md` as backup reference
- [ ] Repo URL ready to share with audience: https://github.com/nrsundar/pg-agent-demo-v2
