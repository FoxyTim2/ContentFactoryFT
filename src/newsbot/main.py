from __future__ import annotations

import asyncio
import logging

from newsbot.config import load_settings
from newsbot.llm import NoOpContentProcessor, OpenAIContentProcessor
from newsbot.publisher import TelegramBotPublisher
from newsbot.state import MessageKey, StateStore
from newsbot.telegram_client import TelegramSourceReader


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


async def run() -> None:
    settings = load_settings()

    reader = TelegramSourceReader(
        api_id=settings.tg_api_id,
        api_hash=settings.tg_api_hash,
        session_name=settings.tg_session_name,
    )
    await reader.connect()

    publisher = TelegramBotPublisher(settings.tg_bot_token)
    state = StateStore(settings.state_db_path)

    if settings.openai_api_key:
        processor = OpenAIContentProcessor(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
        logging.info("OpenAI processor enabled")
    else:
        processor = NoOpContentProcessor()
        logging.info("OPENAI_API_KEY not set, using no-op processor")

    while True:
        try:
            messages = await reader.fetch_recent_messages(
                settings.tg_source_channels,
                settings.lookback_hours,
            )

            messages.sort(key=lambda m: m.date)

            for msg in messages:
                key = MessageKey(source_chat=msg.source_chat, message_id=msg.message_id)
                if state.is_processed(key):
                    continue

                prepared = processor.prepare(msg.text, msg.url)
                final_text = f"{prepared.title}\n\n{prepared.body}"
                publisher.post(settings.tg_target_chat, final_text)
                state.mark_processed(key)
                logging.info("Posted message %s:%s", msg.source_chat, msg.message_id)
        except Exception as exc:
            logging.exception("Cycle failed: %s", exc)

        await asyncio.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    asyncio.run(run())
