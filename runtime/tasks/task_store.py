"""Persistent SQLite storage for tasks using WAL mode."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime
from typing import Optional
from loguru import logger

from runtime.tasks.task_models import Task, TaskPriority, TaskStatus, TaskStep


class TaskStore:
    """
    Thread-safe SQLite store for tasks.

    Uses WAL mode for concurrent access (matching db_manager.py pattern).
    Each thread gets its own connection; writes are serialized via a lock.
    Database: memory/tasks.db
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            from config import get_config
            cfg = get_config()
            db_dir = os.path.join(os.path.dirname(cfg.app.db_path), "..", "memory")
        else:
            db_dir = os.path.dirname(db_path)

        self.db_path = db_path or os.path.join(os.path.abspath(db_dir), "tasks.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.RLock()
        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create a connection for the current thread."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-8000")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self):
        """Initialize database schema. Runs once at startup."""
        conn = self._get_connection()
        with self._lock:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id          TEXT PRIMARY KEY,
                    title       TEXT NOT NULL,
                    description TEXT,
                    status      TEXT NOT NULL,
                    priority    TEXT NOT NULL,
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL,
                    metadata    TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS task_steps (
                    id          TEXT PRIMARY KEY,
                    task_id     TEXT NOT NULL,
                    title       TEXT NOT NULL,
                    status      TEXT NOT NULL,
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                );

                CREATE INDEX IF NOT EXISTS idx_task_steps_task_id
                    ON task_steps(task_id);
            """)
            conn.commit()
        logger.info("TaskStore initialized: {} (WAL mode)", self.db_path)

    def create_task(self, task: Task) -> Task:
        """Insert a new task into the store."""
        conn = self._get_connection()
        data = task.to_dict()
        with self._lock:
            conn.execute(
                "INSERT INTO tasks (id, title, description, status, priority, "
                "created_at, updated_at, metadata) VALUES (?,?,?,?,?,?,?,?)",
                (
                    data["id"], data["title"], data["description"],
                    data["status"], data["priority"],
                    data["created_at"], data["updated_at"],
                    json.dumps(data["metadata"]),
                ),
            )
            self._insert_steps(conn, task)
            conn.commit()
        logger.debug("Task created: {} ({})", task.id, task.title)
        return task

    def update_task(self, task: Task) -> Task:
        """Update an existing task in the store."""
        conn = self._get_connection()
        data = task.to_dict()
        with self._lock:
            conn.execute(
                "UPDATE tasks SET title=?, description=?, status=?, priority=?, "
                "updated_at=?, metadata=? WHERE id=?",
                (
                    data["title"], data["description"],
                    data["status"], data["priority"],
                    data["updated_at"], json.dumps(data["metadata"]),
                    data["id"],
                ),
            )
            conn.execute("DELETE FROM task_steps WHERE task_id=?", (task.id,))
            self._insert_steps(conn, task)
            conn.commit()
        logger.debug("Task updated: {} ({})", task.id, task.title)
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve a task by ID, or None if not found."""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT * FROM tasks WHERE id=?", (task_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_task(conn, row)

    def list_tasks(self, status: TaskStatus = None) -> list[Task]:
        """List all tasks, optionally filtered by status."""
        conn = self._get_connection()
        if status:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status=? ORDER BY created_at DESC",
                (status.value,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_task(conn, row) for row in rows]

    def delete_task(self, task_id: str) -> bool:
        """Delete a task and its steps. Returns True if deleted."""
        conn = self._get_connection()
        with self._lock:
            conn.execute("DELETE FROM task_steps WHERE task_id=?", (task_id,))
            cursor = conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
        if deleted:
            logger.debug("Task deleted: {}", task_id)
        return deleted

    def close(self):
        """Close the current thread's connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            try:
                self._local.conn.close()
            except Exception as e:
                logger.debug("TaskStore connection close error: {}", e)
            self._local.conn = None

    def close_all(self):
        """Close all connections (call at shutdown)."""
        self.close()

    # ── Internal helpers ──────────────────────────────────

    def _insert_steps(self, conn: sqlite3.Connection, task: Task):
        """Insert all steps for a task."""
        for step in task.steps:
            sdata = step.to_dict()
            conn.execute(
                "INSERT INTO task_steps (id, task_id, title, status, "
                "created_at, updated_at) VALUES (?,?,?,?,?,?)",
                (
                    sdata["id"], task.id, sdata["title"],
                    sdata["status"], sdata["created_at"], sdata["updated_at"],
                ),
            )

    def _row_to_task(self, conn: sqlite3.Connection, row: sqlite3.Row) -> Task:
        """Convert a database row to a Task object, loading steps."""
        task = Task(
            id=row["id"],
            title=row["title"],
            description=row["description"] or "",
            status=TaskStatus(row["status"]),
            priority=TaskPriority(row["priority"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )
        step_rows = conn.execute(
            "SELECT * FROM task_steps WHERE task_id=? ORDER BY created_at",
            (task.id,),
        ).fetchall()
        task.steps = [
            TaskStep(
                id=s["id"],
                title=s["title"],
                status=TaskStatus(s["status"]),
                created_at=datetime.fromisoformat(s["created_at"]),
                updated_at=datetime.fromisoformat(s["updated_at"]),
            )
            for s in step_rows
        ]
        return task


__all__ = ["TaskStore"]