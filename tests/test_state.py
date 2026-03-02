import tempfile
import unittest

from newsbot.state import MessageKey, StateStore


class StateStoreTests(unittest.TestCase):
    def test_mark_processed_persists_and_prevents_duplicates(self):
        with tempfile.NamedTemporaryFile() as tmp:
            store = StateStore(tmp.name)
            key = MessageKey(source_chat='@source', message_id=42)

            self.assertFalse(store.is_processed(key))
            store.mark_processed(key)
            self.assertTrue(store.is_processed(key))

            # idempotent insert should not raise
            store.mark_processed(key)
            self.assertTrue(store.is_processed(key))

    def test_pending_approval_flow(self):
        with tempfile.NamedTemporaryFile() as tmp:
            store = StateStore(tmp.name)
            key = MessageKey(source_chat='@source', message_id=7)

            store.mark_pending_approval(key, 'draft text')
            self.assertTrue(store.is_processed(key))
            self.assertEqual(store.get_pending_text(key), 'draft text')

            store.mark_processed(key)
            self.assertIsNone(store.get_pending_text(key))


if __name__ == '__main__':
    unittest.main()
