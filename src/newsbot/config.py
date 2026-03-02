from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from newsbot.settings_store import SettingsStore, bootstrap_from_env


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
    analytics_mode: bool
    tg_moderation_chat: str | None


def load_settings() -> Settings:
    load_dotenv()

    state_db_path = os.getenv("STATE_DB_PATH", "state.db")
    store = SettingsStore(state_db_path)
    env = dict(os.environ)
    bootstrap_from_env(store, env, _bootstrap_keys())

    source_channels = [
        item.strip()
        for item in _get_value(store, env, "TG_SOURCE_CHANNELS", "").split(",")
        if item.strip()
    ]

    if not source_channels:
        raise ValueError("TG_SOURCE_CHANNELS is required")

    tg_api_id = _required(store, env, "TG_API_ID")

    return Settings(
        tg_api_id=int(tg_api_id),
        tg_api_hash=_required(store, env, "TG_API_HASH"),
        tg_session_name=_get_value(store, env, "TG_SESSION_NAME", "content_factory_session"),
        tg_bot_token=_required(store, env, "TG_BOT_TOKEN"),
        tg_target_chat=_required(store, env, "TG_TARGET_CHAT"),
        tg_source_channels=source_channels,
        poll_interval_seconds=int(_get_value(store, env, "POLL_INTERVAL_SECONDS", "300")),
        lookback_hours=int(_get_value(store, env, "LOOKBACK_HOURS", "24")),
        openai_api_key=_get_value(store, env, "OPENAI_API_KEY", "") or None,
        openai_model=_get_value(store, env, "OPENAI_MODEL", "gpt-4o-mini"),
        state_db_path=state_db_path,
        analytics_mode=_bool_value(_get_value(store, env, "ANALYTICS_MODE", "false")),
        tg_moderation_chat=_get_value(store, env, "TG_MODERATION_CHAT", "") or None,
    )


def _required(store: SettingsStore, env: dict[str, str], name: str) -> str:
    value = _get_value(store, env, name, "")
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _get_value(store: SettingsStore, env: dict[str, str], key: str, default: str) -> str:
    value = store.get(key)
    if value is not None:
        return value
    return env.get(key, default)


def _bool_value(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _bootstrap_keys() -> list[str]:
    return [
        "TG_API_ID",
        "TG_API_HASH",
        "TG_SESSION_NAME",
        "TG_BOT_TOKEN",
        "TG_TARGET_CHAT",
        "TG_SOURCE_CHANNELS",
        "POLL_INTERVAL_SECONDS",
        "LOOKBACK_HOURS",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "ANALYTICS_MODE",
        "TG_MODERATION_CHAT",
    ]
