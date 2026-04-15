-- ============================================================
-- pg-agent-demo  |  Live Query Sheet
-- Run these after executing the demo to inspect agent state
-- Usage:  psql $DATABASE_URL -f demo/query_sheet.sql
-- ============================================================

-- ── 1. Conversation memory ───────────────────────────────────
-- What did the agent remember during the session?
SELECT
    m.id,
    m.role,
    m.content,
    m.created_at
FROM messages m
ORDER BY m.created_at;


-- ── 2. Embeddings stored ─────────────────────────────────────
-- Vector representations attached to each message
SELECT
    e.id,
    e.message_id,
    e.embedding,
    e.created_at
FROM embeddings e
ORDER BY e.created_at;


-- ── 3. Tool registry ─────────────────────────────────────────
-- All tools the agent can discover and invoke
SELECT
    name,
    description,
    tool_type,
    keyword_hint,
    requires_approval
FROM tools_registry
ORDER BY id;


-- ── 4. Tool executions (audit log) ───────────────────────────
-- Every tool call the agent made, with input and output
SELECT
    tc.id,
    tc.tool_name,
    tc.input_payload,
    tc.output_payload,
    tc.created_at
FROM tool_calls tc
ORDER BY tc.created_at;


-- ── 5. Workflow state ─────────────────────────────────────────
-- Lifecycle state of every agent request
SELECT
    w.id,
    w.query_text,
    w.status,
    w.last_message,
    w.created_at,
    w.updated_at
FROM workflows w
ORDER BY w.created_at;


-- ── 6. Approval guardrails ────────────────────────────────────
-- Pending, approved, or rejected approval records
SELECT
    a.id,
    a.workflow_id,
    a.tool_name,
    a.status,
    a.reason,
    a.created_at,
    a.decided_at
FROM approvals a
ORDER BY a.created_at;


-- ── 7. Sales data (source of truth) ──────────────────────────
-- Raw data the sales analysis tool queries
SELECT
    region,
    product_name,
    revenue,
    sold_at
FROM sales_data
ORDER BY sold_at;


-- ── 8. Revenue by region (what the tool computed) ────────────
-- Reproduce the tool result directly in SQL
SELECT
    region,
    SUM(revenue)::numeric(12,2) AS total_revenue
FROM sales_data
GROUP BY region
ORDER BY total_revenue DESC;


-- ── 9. Hybrid retrieval example (pgvector) ───────────────────
-- Find messages whose embedding is closest to a sample vector
-- Replace the literal vector with a real query embedding in production
SELECT
    m.role,
    m.content,
    e.embedding <=> '[0.3, 0.5, 0.2]'::vector AS distance
FROM embeddings e
JOIN messages m ON m.id = e.message_id
ORDER BY distance
LIMIT 5;


-- ── 10. Full session audit ────────────────────────────────────
-- Join everything into one readable audit trail
SELECT
    w.query_text,
    w.status        AS workflow_status,
    tc.tool_name,
    tc.created_at   AS tool_called_at,
    a.status        AS approval_status
FROM workflows w
LEFT JOIN tool_calls tc ON tc.workflow_id = w.id
LEFT JOIN approvals  a  ON a.workflow_id  = w.id
ORDER BY w.created_at;
