from __future__ import annotations

import asyncio
import logging

from newsbot.analytics_pipeline import run_analytics_mode
from newsbot.config import load_settings
from newsbot.llm import NoOpContentProcessor, OpenAIContentProcessor
from newsbot.moderation import MarketingModerator, NoOpMarketingClassifier, OpenAIMarketingClassifier
from newsbot.publisher import TelegramBotPublisher
from newsbot.state import MessageKey, StateStore
from newsbot.telegram_client import TelegramSourceReader


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


async def run() -> None:
    settings = load_settings()

    if settings.analytics_mode:
        logging.info("ANALYTICS_MODE=true, running analytics moderation pipeline")
        await run_analytics_mode(settings)
        return

    reader = TelegramSourceReader(
        api_id=settings.tg_api_id,
        api_hash=settings.tg_api_hash,
        session_name=settings.tg_session_name,
    )
    await reader.connect()

    publisher = TelegramBotPublisher(settings.tg_bot_token)
    state = StateStore(settings.state_db_path)

    if settings.openai_api_key:
        try:
            processor = OpenAIContentProcessor(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
            )
            logging.info("OpenAI processor enabled")
        except Exception as exc:
            processor = NoOpContentProcessor()
            logging.exception(
                "OpenAI processor unavailable, falling back to no-op processor: %s",
                exc,
            )
    else:
        processor = NoOpContentProcessor()
        logging.info("OPENAI_API_KEY not set, using no-op processor")

    if settings.openai_api_key:
        try:
            moderation_classifier = OpenAIMarketingClassifier(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
            )
            logging.info("OpenAI moderation classifier enabled")
        except Exception as exc:
            moderation_classifier = NoOpMarketingClassifier()
            logging.exception(
                "OpenAI moderation unavailable, falling back to no-op classifier: %s",
                exc,
            )
    else:
        moderation_classifier = NoOpMarketingClassifier()

    moderator = MarketingModerator(classifier=moderation_classifier)

    while True:
        try:
            messages = await reader.fetch_recent_messages(
                settings.tg_source_channels,
                settings.lookback_hours,
            )

            messages.sort(key=lambda m: m.date)
        except Exception as exc:
            logging.exception("Cycle fetch failed: %s", exc)
            await asyncio.sleep(settings.poll_interval_seconds)
            continue

        for msg in messages:
            key = MessageKey(source_chat=msg.source_chat, message_id=msg.message_id)
            if state.is_processed(key):
                continue

            try:
                moderation_decision = moderator.is_marketing(msg.text)
                if moderation_decision.is_marketing:
                    logging.info(
                        "Skipped marketing message %s:%s, reason=%s",
                        msg.source_chat,
                        msg.message_id,
                        moderation_decision.reason,
                    )
                    state.mark_processed(key)
                    continue

                prepared = processor.prepare(msg.text, msg.url)
                final_text = f"{prepared.title}\n\n{prepared.body}"

                if msg.has_photo and (msg.photo_file_id or msg.photo_bytes):
                    publisher.post_with_photo(
                        settings.tg_target_chat,
                        final_text,
                        photo_file_id=msg.photo_file_id,
                        photo_bytes=msg.photo_bytes,
                    )
                else:
                    publisher.post(settings.tg_target_chat, final_text)

                state.mark_processed(key)
                logging.info("Posted message %s:%s", msg.source_chat, msg.message_id)
            except Exception as exc:
                logging.exception(
                    "Failed processing message %s:%s: %s",
                    msg.source_chat,
                    msg.message_id,
                    exc,
                )

        await asyncio.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    asyncio.run(run())
