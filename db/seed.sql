INSERT INTO conversations (id, user_id, title)
VALUES (1, 'demo-user', 'Conference demo conversation')
ON CONFLICT DO NOTHING;

INSERT INTO messages (id, conversation_id, role, content)
VALUES
    (1, 1, 'user', 'How are sales trending this quarter?'),
    (2, 1, 'assistant', 'I can review the latest sales data and summarize the strongest region.')
ON CONFLICT DO NOTHING;

INSERT INTO embeddings (message_id, embedding)
VALUES
    (1, '[0.90,0.10,0.20]'),
    (2, '[0.10,0.85,0.30]')
ON CONFLICT DO NOTHING;

INSERT INTO tools_registry (name, description, tool_type, keyword_hint, requires_approval, sql_template)
VALUES
    (
        'run_sales_analysis',
        'Summarize revenue by region so the agent can answer sales performance questions.',
        'sql',
        'sales,revenue,region,analysis,trend',
        FALSE,
        'SELECT region, SUM(revenue) AS total_revenue FROM sales_data GROUP BY region ORDER BY total_revenue DESC;'
    ),
    (
        'issue_refund',
        'Mock refund tool included to demonstrate the approval workflow.',
        'sql',
        'refund,credit,return',
        TRUE,
        'SELECT ''Refund requests require downstream approval'' AS note;'
    )
ON CONFLICT (name) DO NOTHING;

INSERT INTO sales_data (region, product_name, revenue, sold_at)
VALUES
    ('North', 'Analytics Suite', 12000.00, '2026-03-02'),
    ('North', 'Forecast Pro', 18000.00, '2026-03-18'),
    ('South', 'Analytics Suite', 9000.00, '2026-03-05'),
    ('West', 'Forecast Pro', 23000.00, '2026-03-11'),
    ('West', 'Agent Console', 15000.00, '2026-03-27'),
    ('East', 'Agent Console', 8000.00, '2026-03-22')
ON CONFLICT DO NOTHING;
