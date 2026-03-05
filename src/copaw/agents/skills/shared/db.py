# -*- coding: utf-8 -*-
"""Agent log persistence utility for skill scripts.

Writes agent execution records to SQLite (dev) or PostgreSQL (prod).
Scripts import this and call save_agent_log() to persist input/output/runtime.

Fields map to spec:  runId → run_id,  execId → exec_id,  agentID → agent_id,
                     inputContent → input_content,  outputContent → output_content,
                     runtime → runtime (ms)
"""
import json
import os
import sqlite3
import time
from pathlib import Path

DB_PATH = os.environ.get(
    "AGENT_LOG_DB",
    str(Path.home() / ".copaw" / "agent_logs.db"),
)


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_logs (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id         TEXT NOT NULL,
            exec_id        TEXT NOT NULL,
            agent_id       TEXT NOT NULL,
            input_content  TEXT,
            output_content TEXT,
            runtime        INTEGER,
            error_msg      TEXT,
            extra          TEXT,
            created_at     TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_exec_id ON agent_logs(exec_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_run_id  ON agent_logs(run_id)")
    conn.commit()
    return conn


def save_agent_log(
    run_id: str,
    exec_id: str,
    agent_id: str,
    input_content: str | None = None,
    output_content: str | None = None,
    runtime: int = 0,
    error_msg: str | None = None,
    extra: dict | None = None,
) -> None:
    """Persist an agent execution record.

    Args:
        run_id:         runId  – unique ID for this sub-agent run (uuid4)
        exec_id:        execId – main execution ID, passed through from orchestrator
        agent_id:       agentID – unique identifier for the agent (e.g. "qichacha_query")
        input_content:  inputContent – JSON string of input data
        output_content: outputContent – JSON string of output data; None on failure
        runtime:        runtime – elapsed milliseconds
        error_msg:      error message if failed
        extra:          optional extra dict (stored as JSON)
    """
    try:
        conn = _get_conn()
        conn.execute(
            """INSERT INTO agent_logs
               (run_id, exec_id, agent_id, input_content, output_content, runtime, error_msg, extra)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                exec_id,
                agent_id,
                input_content,
                output_content,
                runtime,
                error_msg,
                json.dumps(extra) if extra else None,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        # Log persistence must never crash the main script
        import sys
        print(f"[db] save_agent_log failed: {e}", file=sys.stderr)
