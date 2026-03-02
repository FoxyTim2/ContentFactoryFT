import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from newsbot.main import run
from newsbot.telegram_client import SourceMessage


class _StopLoop(Exception):
    pass


class MainPublishingTests(unittest.IsolatedAsyncioTestCase):
    async def _run_once_with_message(self, message: SourceMessage):
        settings = SimpleNamespace(
            analytics_mode=False,
            tg_api_id=1,
            tg_api_hash='hash',
            tg_session_name='session',
            tg_bot_token='token',
            state_db_path=':memory:',
            openai_api_key=None,
            openai_model='gpt',
            tg_source_channels=['@source'],
            lookback_hours=1,
            poll_interval_seconds=0,
            tg_target_chat='@target',
        )

        reader = MagicMock()
        reader.connect = AsyncMock()
        reader.fetch_recent_messages = AsyncMock(return_value=[message])

        publisher = MagicMock()
        state = MagicMock()
        state.is_processed.return_value = False

        prepared = SimpleNamespace(title='Заголовок', body='Текст\n\nИсточник: https://t.me/source/1')
        processor = MagicMock()
        processor.prepare.return_value = prepared

        with (
            patch('newsbot.main.load_settings', return_value=settings),
            patch('newsbot.main.TelegramSourceReader', return_value=reader),
            patch('newsbot.main.TelegramBotPublisher', return_value=publisher),
            patch('newsbot.main.StateStore', return_value=state),
            patch('newsbot.main.NoOpContentProcessor', return_value=processor),
            patch('newsbot.main.asyncio.sleep', new=AsyncMock(side_effect=_StopLoop())),
        ):
            with self.assertRaises(_StopLoop):
                await run()

        return publisher, state, processor

    async def test_run_publishes_with_photo_when_media_present(self):
        msg = SourceMessage(
            source_chat='@source',
            message_id=1,
            text='text',
            date=datetime.now(timezone.utc),
            url='https://t.me/source/1',
            has_photo=True,
            photo_file_id='abc',
        )

        publisher, state, _ = await self._run_once_with_message(msg)

        publisher.post_with_photo.assert_called_once()
        publisher.post.assert_not_called()
        state.mark_processed.assert_called_once()

    async def test_run_publishes_text_when_no_media_present(self):
        msg = SourceMessage(
            source_chat='@source',
            message_id=2,
            text='text',
            date=datetime.now(timezone.utc),
            url='https://t.me/source/2',
            has_photo=False,
        )

        publisher, state, _ = await self._run_once_with_message(msg)

        publisher.post.assert_called_once()
        publisher.post_with_photo.assert_not_called()
        state.mark_processed.assert_called_once()

    async def test_run_skips_marketing_messages(self):
        msg = SourceMessage(
            source_chat='@source',
            message_id=3,
            text='Подпишись и купи курс со скидкой',
            date=datetime.now(timezone.utc),
            url='https://t.me/source/3',
            has_photo=False,
        )

        publisher, state, processor = await self._run_once_with_message(msg)

        publisher.post.assert_not_called()
        publisher.post_with_photo.assert_not_called()
        processor.prepare.assert_not_called()
        state.mark_processed.assert_called_once()


if __name__ == '__main__':
    unittest.main()
