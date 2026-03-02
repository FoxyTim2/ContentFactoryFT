from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re

try:
    from openai import OpenAI
except ImportError:  # optional dependency at runtime
    OpenAI = None


@dataclass(frozen=True)
class PreparedPost:
    title: str
    body: str


class ContentProcessor:
    def prepare(self, text: str, source_url: str | None) -> PreparedPost:
        raise NotImplementedError


class NoOpContentProcessor(ContentProcessor):
    def prepare(self, text: str, source_url: str | None) -> PreparedPost:
        excerpt = text.strip()
        if len(excerpt) > 900:
            excerpt = excerpt[:900] + "..."
        title = "Новость из отслеживаемого канала"
        body = excerpt
        if source_url:
            body = f"{body}\n\nИсточник: {source_url}"
        return PreparedPost(title=title, body=body)


class OpenAIContentProcessor(ContentProcessor):
    MAX_TITLE_LENGTH = 90
    MAX_BODY_LENGTH = 1200

    def __init__(self, api_key: str, model: str) -> None:
        if OpenAI is None:
            raise RuntimeError("openai package is required for OpenAIContentProcessor")
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def prepare(self, text: str, source_url: str | None) -> PreparedPost:
        prompt = (
            "Ты редактор новостей от лица нашей группы. Перепиши текст на русском "
            "(если уже русский — оставь русский), сохрани исходный смысл и факты без "
            "добавления новых деталей. Формулировки должны быть краткими и понятными. "
            "Верни СТРОГО JSON-объект вида {\"title\":\"...\",\"body\":\"...\"} "
            "без markdown и дополнительных полей. Ограничения: title <= 90 символов, "
            "body <= 1200 символов."
        )

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.2,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "prepared_post",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "body": {"type": "string"},
                            },
                            "required": ["title", "body"],
                            "additionalProperties": False,
                        },
                    },
                },
            )
            raw = (response.choices[0].message.content or "").strip()
            payload = self._parse_payload(raw)
            title, body = self._validate_and_trim_payload(payload)
        except Exception as exc:
            logging.exception("OpenAI prepare failed, using no-op fallback: %s", exc)
            excerpt = text.strip()
            if len(excerpt) > 900:
                excerpt = excerpt[:900] + "..."
            title = "Новость из отслеживаемого канала"
            body = excerpt

        body = self._append_source_line(body, source_url)

        return PreparedPost(title=title, body=body)

    @classmethod
    def _validate_and_trim_payload(cls, payload: dict[str, object]) -> tuple[str, str]:
        if set(payload.keys()) != {"title", "body"}:
            raise ValueError("OpenAI payload must contain only title and body")

        title = str(payload["title"]).strip() or "Новость"
        body = str(payload["body"]).strip()

        if len(title) > cls.MAX_TITLE_LENGTH:
            title = title[: cls.MAX_TITLE_LENGTH - 3].rstrip() + "..."
        if len(body) > cls.MAX_BODY_LENGTH:
            body = body[: cls.MAX_BODY_LENGTH - 3].rstrip() + "..."
        return title, body

    @staticmethod
    def _append_source_line(body: str, source_url: str | None) -> str:
        if not source_url:
            return body

        source_line = f"Источник: {source_url}"
        cleaned = body.strip()
        if cleaned.endswith(source_line):
            return cleaned
        return f"{cleaned}\n\n{source_line}" if cleaned else source_line

    @staticmethod
    def _parse_payload(raw: str) -> dict[str, object]:
        """Parse model output to JSON even when it comes wrapped in markdown/text."""
        cleaned = raw.strip()
        if not cleaned:
            raise ValueError("OpenAI returned empty content")

        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.S)
        if fence_match:
            cleaned = fence_match.group(1)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # If model added comments before/after JSON, salvage the first JSON object.
            object_match = re.search(r"\{.*\}", cleaned, flags=re.S)
            if object_match:
                return json.loads(object_match.group(0))
            raise
