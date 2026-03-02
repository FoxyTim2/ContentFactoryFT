from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
from telethon.tl.custom.message import Message


@dataclass(frozen=True)
class SourceMessage:
    source_chat: str
    message_id: int
    text: str
    date: datetime
    url: str | None
    has_photo: bool = False
    photo_file_id: str | None = None
    photo_bytes: bytes | None = None


class TelegramSourceReader:
    def __init__(self, api_id: int, api_hash: str, session_name: str) -> None:
        self._client = TelegramClient(session_name, api_id, api_hash)

    async def connect(self) -> None:
        await self._client.start()

    async def fetch_recent_messages(
        self, channels: list[str], lookback_hours: int
    ) -> list[SourceMessage]:
        min_date = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        results: list[SourceMessage] = []

        for channel in channels:
            async for message in self._client.iter_messages(channel, limit=100):
                if not isinstance(message, Message):
                    continue
                if message.date and message.date < min_date:
                    break
                if not message.text:
                    continue

                photo = getattr(message, "photo", None)
                photo_file_id = None
                if photo is not None:
                    photo_id = getattr(photo, "id", None)
                    if photo_id is not None:
                        photo_file_id = str(photo_id)

                results.append(
                    SourceMessage(
                        source_chat=channel,
                        message_id=message.id,
                        text=message.text,
                        date=message.date or datetime.now(timezone.utc),
                        url=_message_url(channel, message.id),
                        has_photo=photo is not None,
                        photo_file_id=photo_file_id,
                    )
                )
        return results



def _message_url(channel: str, message_id: int) -> str | None:
    clean = channel.replace("@", "").strip()
    if not clean:
        return None
    return f"https://t.me/{clean}/{message_id}"
