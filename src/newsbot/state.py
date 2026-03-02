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
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (source_chat, message_id)
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
