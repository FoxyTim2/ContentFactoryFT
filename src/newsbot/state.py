from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class MessageKey:
    source_chat: str
    message_id: int


class StateStore:
    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_messages (
                source_chat TEXT NOT NULL,
                message_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'published',
                prepared_text TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (source_chat, message_id)
            )
            """
        )
        if not self._has_column("processed_messages", "status"):
            self._conn.execute(
                "ALTER TABLE processed_messages ADD COLUMN status TEXT NOT NULL DEFAULT 'published'"
            )
        if not self._has_column("processed_messages", "prepared_text"):
            self._conn.execute(
                "ALTER TABLE processed_messages ADD COLUMN prepared_text TEXT"
            )
        self._conn.commit()

    def is_processed(self, key: MessageKey) -> bool:
        cursor = self._conn.execute(
            "SELECT 1 FROM processed_messages WHERE source_chat = ? AND message_id = ?",
            (key.source_chat, key.message_id),
        )
        return cursor.fetchone() is not None

    def mark_processed(self, key: MessageKey) -> None:
        self._conn.execute(
            """
            INSERT INTO processed_messages (source_chat, message_id, status)
            VALUES (?, ?, 'published')
            ON CONFLICT(source_chat, message_id) DO UPDATE SET status='published', prepared_text=NULL
            """,
            (key.source_chat, key.message_id),
        )
        self._conn.commit()

    def mark_pending_approval(self, key: MessageKey, prepared_text: str) -> None:
        self._conn.execute(
            """
            INSERT INTO processed_messages (source_chat, message_id, status, prepared_text)
            VALUES (?, ?, 'pending_approval', ?)
            ON CONFLICT(source_chat, message_id)
            DO UPDATE SET status='pending_approval', prepared_text=excluded.prepared_text
            """,
            (key.source_chat, key.message_id, prepared_text),
        )
        self._conn.commit()

    def get_pending_text(self, key: MessageKey) -> str | None:
        cursor = self._conn.execute(
            """
            SELECT prepared_text
            FROM processed_messages
            WHERE source_chat = ? AND message_id = ? AND status = 'pending_approval'
            """,
            (key.source_chat, key.message_id),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return row[0]

    def _has_column(self, table: str, column: str) -> bool:
        cursor = self._conn.execute(f"PRAGMA table_info({table})")
        return any(row[1] == column for row in cursor.fetchall())
