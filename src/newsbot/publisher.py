from __future__ import annotations

import json
from urllib import request


class TelegramBotPublisher:
    def __init__(self, bot_token: str) -> None:
        self._send_message_endpoint = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self._send_photo_endpoint = f"https://api.telegram.org/bot{bot_token}/sendPhoto"

    def post(self, target_chat: str, text: str) -> None:
        self._send_json(
            self._send_message_endpoint,
            {
                "chat_id": target_chat,
                "text": text,
                "disable_web_page_preview": False,
            },
        )

    def post_with_photo(
        self,
        target_chat: str,
        caption: str,
        photo_file_id: str | None = None,
        photo_bytes: bytes | None = None,
    ) -> None:
        try:
            self._send_photo(target_chat, caption, photo_file_id, photo_bytes)
        except Exception:
            self.post(target_chat, caption)

    def _send_json(self, endpoint: str, payload: dict[str, object]) -> None:
        req = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=30) as response:
            if response.status != 200:
                raise RuntimeError(f"Telegram API failed with {response.status}")

    def _send_photo(
        self,
        target_chat: str,
        caption: str,
        photo_file_id: str | None,
        photo_bytes: bytes | None,
    ) -> None:
        if photo_bytes is not None:
            self._send_multipart_photo(target_chat, caption, photo_bytes)
            return

        if not photo_file_id:
            raise ValueError("photo_file_id or photo_bytes must be provided")

        self._send_json(
            self._send_photo_endpoint,
            {
                "chat_id": target_chat,
                "caption": caption,
                "photo": photo_file_id,
            },
        )

    def _send_multipart_photo(self, target_chat: str, caption: str, photo_bytes: bytes) -> None:
        boundary = "----ContentFactoryFTBoundary"
        body = b"".join(
            [
                f"--{boundary}\r\n".encode(),
                b'Content-Disposition: form-data; name="chat_id"\r\n\r\n',
                target_chat.encode("utf-8"),
                b"\r\n",
                f"--{boundary}\r\n".encode(),
                b'Content-Disposition: form-data; name="caption"\r\n\r\n',
                caption.encode("utf-8"),
                b"\r\n",
                f"--{boundary}\r\n".encode(),
                b'Content-Disposition: form-data; name="photo"; filename="photo.jpg"\r\n',
                b"Content-Type: image/jpeg\r\n\r\n",
                photo_bytes,
                b"\r\n",
                f"--{boundary}--\r\n".encode(),
            ]
        )
        req = request.Request(
            self._send_photo_endpoint,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with request.urlopen(req, timeout=30) as response:
            if response.status != 200:
                raise RuntimeError(f"Telegram sendPhoto failed with {response.status}")
