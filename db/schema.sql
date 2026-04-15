CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS conversations (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE conversations IS 'Top-level conversation container for an agent session.';

CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE messages IS 'Ordered message history used for conversational memory retrieval.';
CREATE INDEX IF NOT EXISTS idx_messages_conversation_created_at ON messages (conversation_id, created_at DESC);

CREATE TABLE IF NOT EXISTS embeddings (
    id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    embedding VECTOR(3) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE embeddings IS 'Vector representations for messages used by semantic memory.';
CREATE INDEX IF NOT EXISTS idx_embeddings_message_id ON embeddings (message_id);

CREATE TABLE IF NOT EXISTS tools_registry (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    tool_type TEXT NOT NULL,
    keyword_hint TEXT NOT NULL,
    requires_approval BOOLEAN NOT NULL DEFAULT FALSE,
    sql_template TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE tools_registry IS 'Data-driven registry of tools that the agent can discover and invoke.';
CREATE INDEX IF NOT EXISTS idx_tools_registry_keyword_hint ON tools_registry (keyword_hint);

CREATE TABLE IF NOT EXISTS workflows (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    query_text TEXT NOT NULL,
    status TEXT NOT NULL,
    last_message TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE workflows IS 'State machine record for an agent request from start to finish.';
CREATE INDEX IF NOT EXISTS idx_workflows_conversation_status ON workflows (conversation_id, status);

CREATE TABLE IF NOT EXISTS tool_calls (
    id BIGSERIAL PRIMARY KEY,
    workflow_id BIGINT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    tool_name TEXT NOT NULL,
    input_payload JSONB NOT NULL,
    output_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE tool_calls IS 'Audit log of every tool invocation and its result.';
CREATE INDEX IF NOT EXISTS idx_tool_calls_workflow_id ON tool_calls (workflow_id, created_at DESC);

CREATE TABLE IF NOT EXISTS approvals (
    id BIGSERIAL PRIMARY KEY,
    workflow_id BIGINT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    tool_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected')),
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at TIMESTAMPTZ NULL
);
COMMENT ON TABLE approvals IS 'Guardrail decisions for tools that require explicit approval.';
CREATE INDEX IF NOT EXISTS idx_approvals_workflow_id ON approvals (workflow_id, status);

CREATE TABLE IF NOT EXISTS sales_data (
    id BIGSERIAL PRIMARY KEY,
    region TEXT NOT NULL,
    product_name TEXT NOT NULL,
    revenue NUMERIC(12, 2) NOT NULL,
    sold_at DATE NOT NULL
);
COMMENT ON TABLE sales_data IS 'Sample business fact table used by the conference demo tool.';
CREATE INDEX IF NOT EXISTS idx_sales_data_region_sold_at ON sales_data (region, sold_at DESC);
