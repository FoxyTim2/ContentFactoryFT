from __future__ import annotations

import html
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

from newsbot.settings_store import SettingsStore

load_dotenv()

app = FastAPI(title="NewsBot Admin")
security = HTTPBasic()


class OpenAIKeyPayload(BaseModel):
    openai_api_key: str = Field(min_length=1)


class GeneralSettingsPayload(BaseModel):
    openai_model: str
    poll_interval_seconds: int = Field(ge=5)
    lookback_hours: int = Field(ge=1)
    tg_session_name: str
    analytics_mode: bool


class SourcePayload(BaseModel):
    channel: str


def _auth_guard(credentials: HTTPBasicCredentials = Depends(security)) -> HTTPBasicCredentials:
    expected_username = os.getenv("ADMIN_USERNAME", "admin")
    expected_password = os.getenv("ADMIN_PASSWORD", "admin")
    if credentials.username != expected_username or credentials.password != expected_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials


@app.get("/", response_class=HTMLResponse)
def admin_panel(_: HTTPBasicCredentials = Depends(_auth_guard)) -> str:
    snapshot = _read_snapshot()
    channels = "".join(f"<li>{html.escape(ch)}</li>" for ch in snapshot["tg_source_channels"])
    masked_key = html.escape(snapshot["openai_api_key_masked"])
    return f"""
    <html><body>
      <h1>NewsBot admin</h1>
      <h2>OpenAI</h2>
      <p>API key: {masked_key}</p>
      <h2>General</h2>
      <ul>
        <li>model: {html.escape(snapshot['openai_model'])}</li>
        <li>poll_interval_seconds: {snapshot['poll_interval_seconds']}</li>
        <li>lookback_hours: {snapshot['lookback_hours']}</li>
        <li>tg_session_name: {html.escape(snapshot['tg_session_name'])}</li>
        <li>analytics_mode: {snapshot['analytics_mode']}</li>
      </ul>
      <h2>Sources</h2>
      <ul>{channels}</ul>
    </body></html>
    """


@app.get("/api/settings")
def get_settings(_: HTTPBasicCredentials = Depends(_auth_guard)) -> dict[str, Any]:
    return _read_snapshot()


@app.put("/api/settings/openai-key")
def update_openai_key(payload: OpenAIKeyPayload, _: HTTPBasicCredentials = Depends(_auth_guard)) -> dict[str, str]:
    _store().set("OPENAI_API_KEY", payload.openai_api_key, is_secret=True)
    return {"status": "ok"}


@app.put("/api/settings/general")
def update_general(payload: GeneralSettingsPayload, _: HTTPBasicCredentials = Depends(_auth_guard)) -> dict[str, str]:
    store = _store()
    store.set("OPENAI_MODEL", payload.openai_model)
    store.set("POLL_INTERVAL_SECONDS", str(payload.poll_interval_seconds))
    store.set("LOOKBACK_HOURS", str(payload.lookback_hours))
    store.set("TG_SESSION_NAME", payload.tg_session_name)
    store.set("ANALYTICS_MODE", "true" if payload.analytics_mode else "false")
    return {"status": "ok"}


@app.post("/api/settings/sources")
def add_source(payload: SourcePayload, _: HTTPBasicCredentials = Depends(_auth_guard)) -> dict[str, list[str]]:
    channel = payload.channel.strip()
    if not channel:
        raise HTTPException(status_code=400, detail="channel is required")
    channels = _channels()
    if channel not in channels:
        channels.append(channel)
        _save_channels(channels)
    return {"channels": channels}


@app.delete("/api/settings/sources/{channel}")
def remove_source(channel: str, _: HTTPBasicCredentials = Depends(_auth_guard)) -> dict[str, list[str]]:
    channels = [item for item in _channels() if item != channel]
    _save_channels(channels)
    return {"channels": channels}


def _read_snapshot() -> dict[str, Any]:
    store = _store()
    openai_api_key = store.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    return {
        "openai_api_key_masked": _mask_secret(openai_api_key),
        "openai_model": store.get("OPENAI_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "tg_source_channels": _channels(),
        "poll_interval_seconds": int(store.get("POLL_INTERVAL_SECONDS") or os.getenv("POLL_INTERVAL_SECONDS", "300")),
        "lookback_hours": int(store.get("LOOKBACK_HOURS") or os.getenv("LOOKBACK_HOURS", "24")),
        "tg_session_name": store.get("TG_SESSION_NAME") or os.getenv("TG_SESSION_NAME", "content_factory_session"),
        "analytics_mode": (store.get("ANALYTICS_MODE") or os.getenv("ANALYTICS_MODE", "false")).lower() in {"1", "true", "yes", "on"},
    }


def _channels() -> list[str]:
    raw = _store().get("TG_SOURCE_CHANNELS") or os.getenv("TG_SOURCE_CHANNELS", "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _save_channels(channels: list[str]) -> None:
    _store().set("TG_SOURCE_CHANNELS", ",".join(channels))


def _mask_secret(value: str) -> str:
    if not value:
        return "(not set)"
    if len(value) <= 4:
        return "****"
    return f"{'*' * (len(value) - 4)}{value[-4:]}"



def _store() -> SettingsStore:
    db_path = os.getenv("STATE_DB_PATH", "state.db")
    return SettingsStore(db_path)
