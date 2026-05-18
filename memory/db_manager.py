import sqlite3
import json
import os
from datetime import datetime
from typing import Optional
from loguru import logger
from config import get_config


class DBManager:
    def __init__(self):
        cfg = get_config()
        self.db_path = cfg.app.db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self):
        conn = self._connect()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL,
                role        TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
                content     TEXT NOT NULL,
                timestamp   TEXT NOT NULL,
                metadata    TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS preferences (
                key         TEXT PRIMARY KEY,
                value       TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS facts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                category    TEXT NOT NULL,
                key         TEXT NOT NULL,
                value       TEXT NOT NULL,
                confidence  REAL DEFAULT 1.0,
                created_at  TEXT NOT NULL,
                UNIQUE(category, key)
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                started_at  TEXT NOT NULL,
                ended_at    TEXT,
                summary     TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_conv_session
                ON conversations(session_id, timestamp);
        """)
        conn.commit()
        logger.info("Database initialized: {}", self.db_path)

    # ── Conversations ──────────────────────────────────────

    def save_message(self, session_id: str, role: str, content: str, metadata: dict = None):
        conn = self._connect()
        conn.execute(
            "INSERT INTO conversations (session_id, role, content, timestamp, metadata) VALUES (?,?,?,?,?)",
            (session_id, role, content, datetime.now().isoformat(), json.dumps(metadata or {}))
        )
        conn.commit()

    def get_history(self, session_id: str, limit: int = 20) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT role, content, timestamp FROM conversations "
            "WHERE session_id=? ORDER BY timestamp DESC LIMIT ?",
            (session_id, limit)
        ).fetchall()
        return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]}
                for r in reversed(rows)]

    def get_recent_context(self, session_id: str, limit: int = 10) -> list[dict]:
        """Returns last N messages as {role, content} for AI prompt injection."""
        history = self.get_history(session_id, limit)
        return [{"role": h["role"], "content": h["content"]} for h in history]

    def search_history(self, query: str, limit: int = 5) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT role, content, timestamp FROM conversations "
            "WHERE content LIKE ? ORDER BY timestamp DESC LIMIT ?",
            (f"%{query}%", limit)
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Preferences ───────────────────────────────────────

    def set_preference(self, key: str, value):
        conn = self._connect()
        conn.execute(
            "INSERT INTO preferences (key, value, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, json.dumps(value), datetime.now().isoformat())
        )
        conn.commit()

    def get_preference(self, key: str, default=None):
        conn = self._connect()
        row = conn.execute("SELECT value FROM preferences WHERE key=?", (key,)).fetchone()
        if row:
            return json.loads(row["value"])
        return default

    def get_all_preferences(self) -> dict:
        conn = self._connect()
        rows = conn.execute("SELECT key, value FROM preferences").fetchall()
        return {r["key"]: json.loads(r["value"]) for r in rows}
    @property

    def preferences(self):
        """Direct preferences access for settings panel."""
        return self.get_all_preferences()

    # ── Facts ─────────────────────────────────────────────

    def save_fact(self, category: str, key: str, value: str, confidence: float = 1.0):
        conn = self._connect()
        conn.execute(
            "INSERT INTO facts (category, key, value, confidence, created_at) VALUES (?,?,?,?,?) "
            "ON CONFLICT(category, key) DO UPDATE SET value=excluded.value, confidence=excluded.confidence",
            (category, key, value, confidence, datetime.now().isoformat())
        )
        conn.commit()

    def get_facts(self, category: str = None) -> list[dict]:
        conn = self._connect()
        if category:
            rows = conn.execute(
                "SELECT category, key, value, confidence FROM facts WHERE category=?",
                (category,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT category, key, value, confidence FROM facts"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_fact(self, category: str, key: str) -> Optional[str]:
        conn = self._connect()
        row = conn.execute(
            "SELECT value FROM facts WHERE category=? AND key=?", (category, key)
        ).fetchone()
        return row["value"] if row else None

    # ── Sessions ──────────────────────────────────────────

    def start_session(self, session_id: str):
        conn = self._connect()
        conn.execute(
            "INSERT OR IGNORE INTO sessions (id, started_at) VALUES (?,?)",
            (session_id, datetime.now().isoformat())
        )
        conn.commit()

    def end_session(self, session_id: str, summary: str = None):
        conn = self._connect()
        conn.execute(
            "UPDATE sessions SET ended_at=?, summary=? WHERE id=?",
            (datetime.now().isoformat(), summary, session_id)
        )
        conn.commit()

    def get_session_count(self) -> int:
        conn = self._connect()
        row = conn.execute("SELECT COUNT(*) as cnt FROM sessions").fetchone()
        return row["cnt"]

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None