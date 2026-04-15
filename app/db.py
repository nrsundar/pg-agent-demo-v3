from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - optional until dependencies are installed
    psycopg = None
    dict_row = None


@dataclass
class DatabaseConfig:
    database_url: str


class InMemoryRepository:
    """Small in-memory adapter used by tests and the local demo fallback."""

    def __init__(self) -> None:
        self._conversation_seq = 1
        self._message_seq = 1
        self._workflow_seq = 1
        self._approval_seq = 1
        self._tool_call_seq = 1
        self.conversations: Dict[int, Dict[str, Any]] = {}
        self.messages: List[Dict[str, Any]] = []
        self.embeddings: List[Dict[str, Any]] = []
        self.tools_registry: List[Dict[str, Any]] = []
        self.tool_calls: List[Dict[str, Any]] = []
        self.workflows: Dict[int, Dict[str, Any]] = {}
        self.approvals: List[Dict[str, Any]] = []
        self.sales_data: List[Dict[str, Any]] = []

    def create_conversation(self, user_id: str, title: str) -> int:
        conversation_id = self._conversation_seq
        self._conversation_seq += 1
        self.conversations[conversation_id] = {
            "id": conversation_id,
            "user_id": user_id,
            "title": title,
        }
        return conversation_id

    def store_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        embedding: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        message = {
            "id": self._message_seq,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
        }
        self._message_seq += 1
        self.messages.append(message)
        if embedding is not None:
            self.embeddings.append(
                {
                    "message_id": message["id"],
                    "embedding": embedding,
                }
            )
        return message

    def get_recent_messages(self, conversation_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        rows = [message for message in self.messages if message["conversation_id"] == conversation_id]
        return rows[-limit:]

    def load_tools(self) -> List[Dict[str, Any]]:
        return list(self.tools_registry)

    def create_workflow(self, conversation_id: int, query_text: str, status: str) -> Dict[str, Any]:
        workflow = {
            "id": self._workflow_seq,
            "conversation_id": conversation_id,
            "query_text": query_text,
            "status": status,
            "last_message": "",
        }
        self._workflow_seq += 1
        self.workflows[workflow["id"]] = workflow
        return workflow

    def update_workflow(self, workflow_id: int, status: str, last_message: str) -> Dict[str, Any]:
        workflow = self.workflows[workflow_id]
        workflow["status"] = status
        workflow["last_message"] = last_message
        return workflow

    def get_workflow(self, workflow_id: int) -> Dict[str, Any]:
        return self.workflows[workflow_id]

    def create_approval(self, workflow_id: int, tool_name: str, reason: str) -> Dict[str, Any]:
        approval = {
            "id": self._approval_seq,
            "workflow_id": workflow_id,
            "tool_name": tool_name,
            "status": "pending",
            "reason": reason,
        }
        self._approval_seq += 1
        self.approvals.append(approval)
        return approval

    def log_tool_call(
        self,
        workflow_id: int,
        tool_name: str,
        input_payload: Dict[str, Any],
        output_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        entry = {
            "id": self._tool_call_seq,
            "workflow_id": workflow_id,
            "tool_name": tool_name,
            "input_payload": input_payload,
            "output_payload": output_payload,
        }
        self._tool_call_seq += 1
        self.tool_calls.append(entry)
        return entry

    def execute_tool(self, tool: Dict[str, Any], query: str) -> Dict[str, Any]:
        if tool["name"] == "run_sales_analysis":
            totals: Dict[str, float] = {}
            for row in self.sales_data:
                totals[row["region"]] = totals.get(row["region"], 0.0) + float(row["revenue"])
            ranked = [
                {"region": region, "total_revenue": amount}
                for region, amount in sorted(totals.items(), key=lambda item: item[1], reverse=True)
            ]
            return {
                "rows": ranked,
                "summary": (
                    f"Top region is {ranked[0]['region']} with revenue {ranked[0]['total_revenue']:.2f}."
                    if ranked
                    else "No sales data found."
                ),
            }
        return {
            "rows": [{"note": "Approval-required tool not executed."}],
            "summary": "Tool execution skipped.",
        }

    def seed_defaults(self) -> None:
        conversation_id = self.create_conversation("demo-user", "Conference demo conversation")
        self.store_message(conversation_id, "user", "How are sales trending this quarter?", [0.9, 0.1, 0.2])
        self.store_message(
            conversation_id,
            "assistant",
            "I can review the latest sales data and summarize the strongest region.",
            [0.1, 0.85, 0.3],
        )
        self.tools_registry = [
            {
                "name": "run_sales_analysis",
                "description": "Summarize revenue by region.",
                "tool_type": "sql",
                "keyword_hint": "sales,revenue,region,analysis,trend",
                "requires_approval": False,
                "sql_template": (
                    "SELECT region, SUM(revenue) AS total_revenue "
                    "FROM sales_data GROUP BY region ORDER BY total_revenue DESC;"
                ),
            },
            {
                "name": "issue_refund",
                "description": "Mock refund tool to demonstrate guardrails.",
                "tool_type": "sql",
                "keyword_hint": "refund,credit,return",
                "requires_approval": True,
                "sql_template": "SELECT 'Refund requests require downstream approval' AS note;",
            },
        ]
        self.sales_data = [
            {"region": "North", "product_name": "Analytics Suite", "revenue": 12000.00, "sold_at": "2026-03-02"},
            {"region": "North", "product_name": "Forecast Pro", "revenue": 18000.00, "sold_at": "2026-03-18"},
            {"region": "South", "product_name": "Analytics Suite", "revenue": 9000.00, "sold_at": "2026-03-05"},
            {"region": "West", "product_name": "Forecast Pro", "revenue": 23000.00, "sold_at": "2026-03-11"},
            {"region": "West", "product_name": "Agent Console", "revenue": 15000.00, "sold_at": "2026-03-27"},
            {"region": "East", "product_name": "Agent Console", "revenue": 8000.00, "sold_at": "2026-03-22"},
        ]


class PostgresRepository:
    """Production adapter that persists agent state in PostgreSQL."""

    def __init__(self, database_url: str) -> None:
        if psycopg is None:
            raise RuntimeError("psycopg is required to use PostgresRepository")
        self.database_url = database_url

    def _connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def create_conversation(self, user_id: str, title: str) -> int:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversations (user_id, title) VALUES (%s, %s) RETURNING id",
                (user_id, title),
            )
            return int(cur.fetchone()["id"])

    def store_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        embedding: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                (
                    "INSERT INTO messages (conversation_id, role, content) "
                    "VALUES (%s, %s, %s) RETURNING id, conversation_id, role, content"
                ),
                (conversation_id, role, content),
            )
            message = cur.fetchone()
            if embedding is not None:
                cur.execute(
                    "INSERT INTO embeddings (message_id, embedding) VALUES (%s, %s)",
                    (message["id"], embedding),
                )
            return message

    def get_recent_messages(self, conversation_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                (
                    "SELECT id, conversation_id, role, content "
                    "FROM messages WHERE conversation_id = %s "
                    "ORDER BY created_at DESC LIMIT %s"
                ),
                (conversation_id, limit),
            )
            rows = cur.fetchall()
            return list(reversed(rows))

    def load_tools(self) -> List[Dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT name, description, tool_type, keyword_hint, requires_approval, sql_template "
                "FROM tools_registry ORDER BY id"
            )
            return cur.fetchall()

    def create_workflow(self, conversation_id: int, query_text: str, status: str) -> Dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                (
                    "INSERT INTO workflows (conversation_id, query_text, status) "
                    "VALUES (%s, %s, %s) "
                    "RETURNING id, conversation_id, query_text, status, last_message"
                ),
                (conversation_id, query_text, status),
            )
            return cur.fetchone()

    def update_workflow(self, workflow_id: int, status: str, last_message: str) -> Dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                (
                    "UPDATE workflows SET status = %s, last_message = %s, updated_at = NOW() "
                    "WHERE id = %s "
                    "RETURNING id, conversation_id, query_text, status, last_message"
                ),
                (status, last_message, workflow_id),
            )
            return cur.fetchone()

    def get_workflow(self, workflow_id: int) -> Dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, conversation_id, query_text, status, last_message FROM workflows WHERE id = %s",
                (workflow_id,),
            )
            return cur.fetchone()

    def create_approval(self, workflow_id: int, tool_name: str, reason: str) -> Dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                (
                    "INSERT INTO approvals (workflow_id, tool_name, status, reason) "
                    "VALUES (%s, %s, 'pending', %s) "
                    "RETURNING id, workflow_id, tool_name, status, reason"
                ),
                (workflow_id, tool_name, reason),
            )
            return cur.fetchone()

    def log_tool_call(
        self,
        workflow_id: int,
        tool_name: str,
        input_payload: Dict[str, Any],
        output_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                (
                    "INSERT INTO tool_calls (workflow_id, tool_name, input_payload, output_payload) "
                    "VALUES (%s, %s, %s::jsonb, %s::jsonb) "
                    "RETURNING id, workflow_id, tool_name"
                ),
                (workflow_id, tool_name, json.dumps(input_payload), json.dumps(output_payload)),
            )
            return cur.fetchone()

    def execute_tool(self, tool: Dict[str, Any], query: str) -> Dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(tool["sql_template"])
            rows = cur.fetchall()
            summary = "No rows returned."
            if rows:
                first_row = rows[0]
                if "region" in first_row and "total_revenue" in first_row:
                    summary = f"Top region is {first_row['region']} with revenue {float(first_row['total_revenue']):.2f}."
                else:
                    summary = f"Tool {tool['name']} returned {len(rows)} row(s)."
            return {"rows": rows, "summary": summary}


def build_repository() -> Any:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return PostgresRepository(database_url)

    repository = InMemoryRepository()
    repository.seed_defaults()
    return repository
