import unittest
from datetime import datetime, timezone

from newsbot.analytics_pipeline import _parse_approve_command
from newsbot.telegram_client import SourceMessage


class AnalyticsPipelineTests(unittest.TestCase):
    def test_parse_approve_command(self):
        msg = SourceMessage(
            source_chat='@moderation',
            message_id=1,
            text='/approve @source 55',
            date=datetime.now(timezone.utc),
            url=None,
        )

        parsed = _parse_approve_command(msg)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.source_chat, '@source')
        self.assertEqual(parsed.message_id, 55)

    def test_parse_approve_command_invalid(self):
        msg = SourceMessage(
            source_chat='@moderation',
            message_id=1,
            text='approve @source 55',
            date=datetime.now(timezone.utc),
            url=None,
        )

        self.assertIsNone(_parse_approve_command(msg))


if __name__ == '__main__':
    unittest.main()
