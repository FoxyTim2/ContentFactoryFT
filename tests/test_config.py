import os
import unittest
from unittest.mock import patch

from newsbot.config import load_settings


class ConfigTests(unittest.TestCase):
    def test_load_settings_reads_review_chat(self):
        fake_env = {
            "TG_API_ID": "1",
            "TG_API_HASH": "hash",
            "TG_BOT_TOKEN": "token",
            "TG_TARGET_CHAT": "@target",
            "TG_SOURCE_CHANNELS": "@source",
            "TG_REVIEW_CHAT": "@review",
        }
        with patch.dict(os.environ, fake_env, clear=True):
            settings = load_settings()

        self.assertEqual(settings.tg_review_chat, "@review")


if __name__ == "__main__":
    unittest.main()
