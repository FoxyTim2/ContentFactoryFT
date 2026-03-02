from __future__ import annotations

import json
from urllib import request


class TelegramBotPublisher:
    def __init__(self, bot_token: str) -> None:
        self._endpoint = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    def post(self, target_chat: str, text: str) -> None:
        payload = json.dumps(
            {
                "chat_id": target_chat,
                "text": text,
                "disable_web_page_preview": False,
            }
        ).encode("utf-8")

        req = request.Request(
            self._endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=30) as response:
            if response.status != 200:
                raise RuntimeError(f"Telegram sendMessage failed with {response.status}")
