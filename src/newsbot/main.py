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


async def _initialize_cursors_if_needed(
    settings,
    reader: TelegramSourceReader,
    state: StateStore,
) -> None:
    if settings.start_mode != "now":
        return

    for channel in settings.tg_source_channels:
        if state.get_cursor(channel) is not None:
            continue
        latest = await reader.get_latest_message_id(channel)
        if latest is None:
            continue
        state.set_cursor(channel, latest)
        logging.info("Initialized cursor for %s to %s", channel, latest)


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

    await _initialize_cursors_if_needed(settings, reader, state)

    while True:
        try:
            publisher.process_admin_commands(
                state=state,
                target_chat=settings.tg_target_chat,
                admin_chat_id=settings.admin_review_chat_id,
            )

            if settings.start_mode == "lookback":
                messages = await reader.fetch_recent_messages(
                    settings.tg_source_channels,
                    settings.lookback_hours,
                )
            else:
                cursor_map = {
                    channel: state.get_cursor(channel) or 0
                    for channel in settings.tg_source_channels
                }
                messages = await reader.fetch_messages_since_cursor(
                    settings.tg_source_channels,
                    cursor_map,
                )

            messages.sort(key=lambda m: m.date)

            for msg in messages:
                key = MessageKey(source_chat=msg.source_chat, message_id=msg.message_id)
                if state.is_processed(key):
                    continue

                result = processor.process_message(msg.text)
                ru_text = result.ru_text.strip()[: settings.max_output_chars]
                if msg.url:
                    ru_text = f"{ru_text}\n\nИсточник: {msg.url}"

                action = result.action
                reason = "auto"

                if result.topic == "russia":
                    if settings.russia_policy == "drop":
                        action = "drop"
                        reason = "russia_topic_drop_policy"
                    else:
                        action = "review"
                        reason = "russia_topic_review_policy"

                if action == "review" and not settings.admin_review_chat_id:
                    action = "drop"
                    reason = "review_chat_not_configured"

                if action == "publish":
                    publisher.post(settings.tg_target_chat, ru_text)
                    logging.info("Published %s:%s", msg.source_chat, msg.message_id)
                elif action == "review":
                    pending_id = state.add_pending(
                        source=msg.source_chat,
                        source_msg_id=msg.message_id,
                        prepared_text=ru_text,
                        reason=reason,
                    )
                    publisher.send_for_review(
                        settings.admin_review_chat_id,
                        ru_text,
                        reason,
                        pending_id,
                    )
                    logging.info(
                        "Sent to review %s:%s reason=%s",
                        msg.source_chat,
                        msg.message_id,
                        reason,
                    )
                else:
                    logging.info(
                        "Dropped %s:%s reason=%s",
                        msg.source_chat,
                        msg.message_id,
                        reason,
                    )

                state.mark_processed(key)
                current_cursor = state.get_cursor(msg.source_chat) or 0
                if msg.message_id > current_cursor:
                    state.set_cursor(msg.source_chat, msg.message_id)
        except Exception as exc:
            logging.exception("Cycle failed: %s", exc)

        await asyncio.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    asyncio.run(run())
