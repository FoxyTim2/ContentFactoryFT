from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from telethon import TelegramClient
from telethon.tl.custom.message import Message


@dataclass(frozen=True)
class SourceMessage:
    source_chat: str
    message_id: int
    text: str
    date: datetime
    url: str | None


class TelegramSourceReader:
    def __init__(self, api_id: int, api_hash: str, session_name: str) -> None:
        self._client = TelegramClient(session_name, api_id, api_hash)

    async def connect(self) -> None:
        await self._client.start()

    async def fetch_recent_messages(
        self, channels: list[str], lookback_hours: int
    ) -> list[SourceMessage]:
        min_date = datetime.now(UTC) - timedelta(hours=lookback_hours)
        results: list[SourceMessage] = []

        for channel in channels:
            async for message in self._client.iter_messages(channel, limit=100):
                if not isinstance(message, Message):
                    continue
                if message.date and message.date < min_date:
                    break
                if not message.text:
                    continue

                results.append(
                    SourceMessage(
                        source_chat=channel,
                        message_id=message.id,
                        text=message.text,
                        date=message.date or datetime.now(UTC),
                        url=_message_url(channel, message.id),
                    )
                )
        return results



def _message_url(channel: str, message_id: int) -> str | None:
    clean = channel.replace("@", "").strip()
    if not clean:
        return None
    return f"https://t.me/{clean}/{message_id}"
