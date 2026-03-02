from __future__ import annotations

import asyncio
import logging
import re

from newsbot.config import Settings
from newsbot.llm import NoOpContentProcessor, OpenAIContentProcessor
from newsbot.publisher import TelegramBotPublisher
from newsbot.state import MessageKey, StateStore
from newsbot.telegram_client import TelegramSourceReader, SourceMessage

APPROVE_PATTERN = re.compile(r"^/approve\s+(?P<source_chat>\S+)\s+(?P<message_id>\d+)\s*$")


async def run_analytics_mode(settings: Settings) -> None:
    if not settings.tg_moderation_chat:
        raise ValueError("TG_MODERATION_CHAT is required when ANALYTICS_MODE=true")

    reader = TelegramSourceReader(
        api_id=settings.tg_api_id,
        api_hash=settings.tg_api_hash,
        session_name=settings.tg_session_name,
    )
    await reader.connect()

    publisher = TelegramBotPublisher(settings.tg_bot_token)
    state = StateStore(settings.state_db_path)
    processor = _build_processor(settings)

    while True:
        await _prepare_drafts(settings, reader, publisher, state, processor)
        await _handle_approvals(settings, reader, publisher, state)
        await asyncio.sleep(settings.poll_interval_seconds)


async def _prepare_drafts(
    settings: Settings,
    reader: TelegramSourceReader,
    publisher: TelegramBotPublisher,
    state: StateStore,
    processor: OpenAIContentProcessor | NoOpContentProcessor,
) -> None:
    try:
        messages = await reader.fetch_recent_messages(
            settings.tg_source_channels,
            settings.lookback_hours,
        )
    except Exception as exc:
        logging.exception("Analytics cycle fetch failed: %s", exc)
        return

    messages.sort(key=lambda m: m.date)
    for msg in messages:
        key = MessageKey(source_chat=msg.source_chat, message_id=msg.message_id)
        if state.is_processed(key):
            continue

        try:
            prepared = processor.prepare(msg.text, msg.url)
            final_text = f"{prepared.title}\n\n{prepared.body}"
            draft_text = _format_draft(msg, final_text)
            publisher.post(settings.tg_moderation_chat or "", draft_text)
            state.mark_pending_approval(key, final_text)
            logging.info(
                "Draft queued for approval %s:%s",
                msg.source_chat,
                msg.message_id,
            )
        except Exception as exc:
            logging.exception(
                "Failed preparing analytics draft %s:%s: %s",
                msg.source_chat,
                msg.message_id,
                exc,
            )


async def _handle_approvals(
    settings: Settings,
    reader: TelegramSourceReader,
    publisher: TelegramBotPublisher,
    state: StateStore,
) -> None:
    try:
        moderation_messages = await reader.fetch_recent_messages(
            [settings.tg_moderation_chat or ""],
            lookback_hours=max(1, settings.lookback_hours),
        )
    except Exception as exc:
        logging.exception("Failed reading moderation approvals: %s", exc)
        return

    moderation_messages.sort(key=lambda m: m.date)
    for msg in moderation_messages:
        approval = _parse_approve_command(msg)
        if approval is None:
            continue

        pending_key = MessageKey(
            source_chat=approval.source_chat,
            message_id=approval.message_id,
        )
        pending_text = state.get_pending_text(pending_key)
        if pending_text is None:
            continue

        publisher.post(settings.tg_target_chat, pending_text)
        state.mark_processed(pending_key)
        logging.info("Published approved analytics post %s:%s", pending_key.source_chat, pending_key.message_id)


def _build_processor(settings: Settings) -> OpenAIContentProcessor | NoOpContentProcessor:
    if settings.openai_api_key:
        try:
            processor = OpenAIContentProcessor(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
            )
            logging.info("OpenAI processor enabled")
            return processor
        except Exception as exc:
            logging.exception(
                "OpenAI processor unavailable, falling back to no-op processor: %s",
                exc,
            )

    logging.info("OPENAI_API_KEY not set or unavailable, using no-op processor")
    return NoOpContentProcessor()


def _format_draft(msg: SourceMessage, final_text: str) -> str:
    return (
        "[DRAFT][ANALYTICS]\n"
        f"source_chat: {msg.source_chat}\n"
        f"message_id: {msg.message_id}\n"
        f"approve: /approve {msg.source_chat} {msg.message_id}\n\n"
        f"{final_text}"
    )


class ApprovalCommand:
    def __init__(self, source_chat: str, message_id: int) -> None:
        self.source_chat = source_chat
        self.message_id = message_id


def _parse_approve_command(msg: SourceMessage) -> ApprovalCommand | None:
    match = APPROVE_PATTERN.match(msg.text.strip())
    if not match:
        return None
    return ApprovalCommand(
        source_chat=match.group("source_chat"),
        message_id=int(match.group("message_id")),
    )
