from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    tg_api_id: int
    tg_api_hash: str
    tg_session_name: str
    tg_bot_token: str
    tg_target_chat: str
    tg_source_channels: list[str]
    poll_interval_seconds: int
    lookback_hours: int
    openai_api_key: str | None
    openai_model: str
    state_db_path: str
    tg_review_chat: str | None


def load_settings() -> Settings:
    load_dotenv()

    source_channels = [
        item.strip()
        for item in os.getenv("TG_SOURCE_CHANNELS", "").split(",")
        if item.strip()
    ]

    if not source_channels:
        raise ValueError("TG_SOURCE_CHANNELS is required")

    tg_api_id = os.getenv("TG_API_ID")
    if not tg_api_id:
        raise ValueError("TG_API_ID is required")

    return Settings(
        tg_api_id=int(tg_api_id),
        tg_api_hash=_required("TG_API_HASH"),
        tg_session_name=os.getenv("TG_SESSION_NAME", "content_factory_session"),
        tg_bot_token=_required("TG_BOT_TOKEN"),
        tg_target_chat=_required("TG_TARGET_CHAT"),
        tg_source_channels=source_channels,
        poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "300")),
        lookback_hours=int(os.getenv("LOOKBACK_HOURS", "24")),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        state_db_path=os.getenv("STATE_DB_PATH", "state.db"),
        tg_review_chat=os.getenv("TG_REVIEW_CHAT") or None,
    )



def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} is required")
    return value
