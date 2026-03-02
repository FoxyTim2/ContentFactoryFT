import sqlite3
import tempfile
import unittest

from newsbot.migrations import run_migrations


class MigrationTests(unittest.TestCase):
    def test_creates_settings_table(self):
        with tempfile.NamedTemporaryFile() as tmp:
            conn = sqlite3.connect(tmp.name)
            run_migrations(conn)
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
            self.assertIsNotNone(cursor.fetchone())


if __name__ == '__main__':
    unittest.main()
