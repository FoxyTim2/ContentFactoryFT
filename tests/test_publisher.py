import unittest
from unittest.mock import patch

from newsbot.publisher import TelegramBotPublisher


class PublisherTests(unittest.TestCase):
    def test_post_with_photo_falls_back_to_text(self):
        publisher = TelegramBotPublisher('token')

        with (
            patch.object(publisher, '_send_photo', side_effect=RuntimeError('boom')),
            patch.object(publisher, 'post') as post_mock,
        ):
            publisher.post_with_photo('@target', 'caption', photo_file_id='file-id')

        post_mock.assert_called_once_with('@target', 'caption')


if __name__ == '__main__':
    unittest.main()
