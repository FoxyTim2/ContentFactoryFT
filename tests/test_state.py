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
            store.mark_processed(key)
            self.assertTrue(store.is_processed(key))

    def test_cursor_and_pending_flow(self):
        with tempfile.NamedTemporaryFile() as tmp:
            store = StateStore(tmp.name)

            self.assertIsNone(store.get_cursor('@source'))
            store.set_cursor('@source', 10)
            self.assertEqual(10, store.get_cursor('@source'))

            pending_id = store.add_pending('@source', 11, 'prepared text', 'russia_topic_review_policy')
            pending = store.get_pending(pending_id)
            self.assertIsNotNone(pending)
            self.assertEqual('pending', pending.status)

            listed = store.list_pending()
            self.assertEqual(1, len(listed))
            self.assertEqual(pending_id, listed[0].id)

            self.assertTrue(store.approve_pending(pending_id))
            self.assertFalse(store.approve_pending(pending_id))


if __name__ == '__main__':
    unittest.main()
