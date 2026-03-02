from __future__ import annotations

import sqlite3
from typing import Iterable

from newsbot.migrations import run_migrations


SECRET_KEYS = {"OPENAI_API_KEY"}


class SettingsStore:
    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        run_migrations(self._conn)

    def get(self, key: str) -> str | None:
        cursor = self._conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None

    def set(self, key: str, value: str, is_secret: bool = False) -> None:
        self._conn.execute(
            """
            INSERT INTO settings (key, value, is_secret, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value=excluded.value,
                is_secret=excluded.is_secret,
                updated_at=CURRENT_TIMESTAMP
            """,
            (key, value, 1 if is_secret else 0),
        )
        self._conn.commit()

    def set_if_missing(self, key: str, value: str, is_secret: bool = False) -> None:
        if self.get(key) is not None:
            return
        self.set(key, value, is_secret=is_secret)

    def delete(self, key: str) -> None:
        self._conn.execute("DELETE FROM settings WHERE key = ?", (key,))
        self._conn.commit()

    def all_values(self) -> dict[str, str]:
        cursor = self._conn.execute("SELECT key, value FROM settings")
        return {row[0]: row[1] for row in cursor.fetchall()}



def bootstrap_from_env(store: SettingsStore, env_values: dict[str, str | None], keys: Iterable[str]) -> None:
    for key in keys:
        value = env_values.get(key)
        if value is None or value == "":
            continue
        store.set_if_missing(key, value, is_secret=key in SECRET_KEYS)
