from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class MessageKey:
    source_chat: str
    message_id: int


@dataclass(frozen=True)
class PendingPost:
    id: int
    source: str
    source_msg_id: int
    prepared_text: str
    reason: str
    status: str


class StateStore:
    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_messages (
                source_chat TEXT NOT NULL,
                message_id INTEGER NOT NULL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (source_chat, message_id)
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS source_cursors (
                source_chat TEXT PRIMARY KEY,
                cursor_message_id INTEGER NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_msg_id INTEGER NOT NULL,
                prepared_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
            )
            """
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
            "INSERT OR IGNORE INTO processed_messages (source_chat, message_id) VALUES (?, ?)",
            (key.source_chat, key.message_id),
        )
        self._conn.commit()

    def get_cursor(self, source_key: str) -> int | None:
        row = self._conn.execute(
            "SELECT cursor_message_id FROM source_cursors WHERE source_chat = ?",
            (source_key,),
        ).fetchone()
        return int(row[0]) if row else None

    def set_cursor(self, source_key: str, msg_id: int) -> None:
        self._conn.execute(
            """
            INSERT INTO source_cursors (source_chat, cursor_message_id)
            VALUES (?, ?)
            ON CONFLICT(source_chat)
            DO UPDATE SET cursor_message_id = excluded.cursor_message_id,
                          updated_at = CURRENT_TIMESTAMP
            """,
            (source_key, msg_id),
        )
        self._conn.commit()

    def add_pending(
        self,
        source: str,
        source_msg_id: int,
        prepared_text: str,
        reason: str,
    ) -> int:
        cur = self._conn.execute(
            """
            INSERT INTO pending_posts (source, source_msg_id, prepared_text, reason, status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (source, source_msg_id, prepared_text, reason),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def list_pending(self) -> list[PendingPost]:
        rows = self._conn.execute(
            """
            SELECT id, source, source_msg_id, prepared_text, reason, status
            FROM pending_posts
            WHERE status = 'pending'
            ORDER BY id ASC
            """
        ).fetchall()
        return [PendingPost(*row) for row in rows]

    def get_pending(self, pending_id: int) -> PendingPost | None:
        row = self._conn.execute(
            """
            SELECT id, source, source_msg_id, prepared_text, reason, status
            FROM pending_posts
            WHERE id = ?
            """,
            (pending_id,),
        ).fetchone()
        return PendingPost(*row) if row else None

    def approve_pending(self, pending_id: int) -> bool:
        cur = self._conn.execute(
            "UPDATE pending_posts SET status='approved' WHERE id=? AND status='pending'",
            (pending_id,),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def reject_pending(self, pending_id: int) -> bool:
        cur = self._conn.execute(
            "UPDATE pending_posts SET status='rejected' WHERE id=? AND status='pending'",
            (pending_id,),
        )
        self._conn.commit()
        return cur.rowcount > 0
