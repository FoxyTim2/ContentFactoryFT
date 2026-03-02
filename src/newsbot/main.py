from __future__ import annotations

import asyncio
import logging

from newsbot.config import load_settings
from newsbot.llm import ContentModerator, NoOpContentProcessor, OpenAIContentProcessor
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
    moderator = ContentModerator(settings.openai_api_key, settings.openai_model)

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
                moderation_before = moderator.assess(msg.text)
                if moderation_before.action == "block":
                    state.mark_processed(key)
                    logging.info(
                        "Blocked message %s:%s (%s)",
                        msg.source_chat,
                        msg.message_id,
                        moderation_before.reason,
                    )
                    continue

                if moderation_before.action == "review":
                    _send_to_review(
                        publisher=publisher,
                        review_chat=settings.tg_review_chat,
                        stage="до редактуры",
                        reason=moderation_before.reason,
                        source_url=msg.url,
                        payload_text=msg.text,
                        source_chat=msg.source_chat,
                        message_id=msg.message_id,
                    )
                    state.mark_processed(key)
                    continue

                prepared = processor.prepare(msg.text, msg.url)
                final_text = f"{prepared.title}\n\n{prepared.body}"

                moderation_after = moderator.assess(final_text)
                if moderation_after.action == "block":
                    state.mark_processed(key)
                    logging.info(
                        "Blocked prepared message %s:%s (%s)",
                        msg.source_chat,
                        msg.message_id,
                        moderation_after.reason,
                    )
                    continue

                if moderation_after.action == "review":
                    _send_to_review(
                        publisher=publisher,
                        review_chat=settings.tg_review_chat,
                        stage="после редактуры",
                        reason=moderation_after.reason,
                        source_url=msg.url,
                        payload_text=final_text,
                        source_chat=msg.source_chat,
                        message_id=msg.message_id,
                    )
                    state.mark_processed(key)
                    continue

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


def _send_to_review(
    publisher: TelegramBotPublisher,
    review_chat: str | None,
    stage: str,
    reason: str,
    source_url: str | None,
    payload_text: str,
    source_chat: str,
    message_id: int,
) -> None:
    if not review_chat:
        logging.warning(
            "Review required for %s:%s but TG_REVIEW_CHAT is not configured",
            source_chat,
            message_id,
        )
        return

    review_text = (
        f"⏸ На согласование ({stage})\n"
        f"Причина: {reason}\n\n"
        f"Источник: {source_url or 'n/a'}\n\n"
        f"Текст:\n{payload_text}"
    )
    publisher.post(review_chat, review_text)
    logging.info(
        "Sent message %s:%s to review (%s)",
        source_chat,
        message_id,
        reason,
    )


if __name__ == "__main__":
    asyncio.run(run())
