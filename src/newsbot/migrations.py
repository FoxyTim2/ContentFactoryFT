from __future__ import annotations

import sqlite3


def run_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
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
    _ensure_column(conn, "processed_messages", "status", "TEXT NOT NULL DEFAULT 'published'")
    _ensure_column(conn, "processed_messages", "prepared_text", "TEXT")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            is_secret INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    _ensure_column(conn, "settings", "is_secret", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "settings", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    conn.commit()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, declaration: str) -> None:
    cursor = conn.execute(f"PRAGMA table_info({table})")
    if any(row[1] == column for row in cursor.fetchall()):
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
