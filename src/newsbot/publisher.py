from __future__ import annotations

import json
from urllib import parse, request

from newsbot.state import StateStore


class TelegramBotPublisher:
    def __init__(self, bot_token: str) -> None:
        self._base = f"https://api.telegram.org/bot{bot_token}"
        self._send_endpoint = f"{self._base}/sendMessage"
        self._updates_endpoint = f"{self._base}/getUpdates"
        self._last_update_id = 0

    def post(self, target_chat: str, text: str) -> None:
        payload = json.dumps(
            {
                "chat_id": target_chat,
                "text": text,
                "disable_web_page_preview": False,
            }
        ).encode("utf-8")

        req = request.Request(
            self._send_endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=30) as response:
            if response.status != 200:
                raise RuntimeError(f"Telegram sendMessage failed with {response.status}")

    def send_for_review(self, admin_chat: str | None, text: str, reason: str, pending_id: int) -> None:
        if not admin_chat:
            return
        review_text = f"🕵️ На модерации #{pending_id}\nПричина: {reason}\n\n{text}"
        self.post(admin_chat, review_text)

    def process_admin_commands(
        self,
        state: StateStore,
        target_chat: str,
        admin_chat_id: str | None,
    ) -> None:
        if not admin_chat_id:
            return

        params = parse.urlencode({"timeout": 0, "offset": self._last_update_id + 1})
        url = f"{self._updates_endpoint}?{params}"
        with request.urlopen(url, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))

        for item in payload.get("result", []):
            self._last_update_id = max(self._last_update_id, int(item.get("update_id", 0)))
            message = item.get("message", {})
            text = str(message.get("text", "")).strip()
            chat_id = str(message.get("chat", {}).get("id", ""))
            if chat_id != str(admin_chat_id):
                continue
            if not text.startswith("/"):
                continue
            self._handle_command(text, chat_id, state, target_chat)

    def _handle_command(self, text: str, chat_id: str, state: StateStore, target_chat: str) -> None:
        if text == "/pending":
            pending = state.list_pending()
            if not pending:
                self.post(chat_id, "Очередь модерации пуста.")
                return
            lines = [f"#{p.id} | {p.source}:{p.source_msg_id} | {p.reason}" for p in pending[:20]]
            self.post(chat_id, "Ожидают:\n" + "\n".join(lines))
            return

        if text.startswith("/approve "):
            pending_id = _extract_int_arg(text)
            if pending_id is None:
                self.post(chat_id, "Используйте: /approve <id>")
                return
            post = state.get_pending(pending_id)
            if not post or post.status != "pending":
                self.post(chat_id, f"Пост #{pending_id} не найден в pending")
                return
            self.post(target_chat, post.prepared_text)
            state.approve_pending(pending_id)
            self.post(chat_id, f"✅ Одобрено и отправлено: #{pending_id}")
            return

        if text.startswith("/reject "):
            pending_id = _extract_int_arg(text)
            if pending_id is None:
                self.post(chat_id, "Используйте: /reject <id>")
                return
            if state.reject_pending(pending_id):
                self.post(chat_id, f"❌ Отклонено: #{pending_id}")
            else:
                self.post(chat_id, f"Пост #{pending_id} не найден в pending")


def _extract_int_arg(command_text: str) -> int | None:
    parts = command_text.split(maxsplit=1)
    if len(parts) != 2:
        return None
    try:
        return int(parts[1].strip())
    except ValueError:
        return None
