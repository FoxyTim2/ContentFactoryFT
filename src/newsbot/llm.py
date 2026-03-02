from __future__ import annotations

from dataclasses import dataclass
import json
import logging

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
    def __init__(self, api_key: str, model: str) -> None:
        if OpenAI is None:
            raise RuntimeError("openai package is required for OpenAIContentProcessor")
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def prepare(self, text: str, source_url: str | None) -> PreparedPost:
        prompt = (
            "Ты редактор новостей. Переведи текст на русский (если уже русский — оставь), "
            "слегка отредактируй для ясности без искажения фактов, и верни JSON формата "
            '{"title":"...","body":"..."}. Заголовок до 90 символов, тело до 1200 символов.'
        )

        try:
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ]

            if hasattr(self._client, "responses"):
                response = self._client.responses.create(
                    model=self._model,
                    input=messages,
                )
                raw = (getattr(response, "output_text", "") or "").strip()
            else:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=0.2,
                )
                raw = (response.choices[0].message.content or "").strip()

            if raw.startswith("```"):
                raw = raw.strip("`")
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            payload = json.loads(raw)
            title = str(payload.get("title", "Новость")).strip() or "Новость"
            body = str(payload.get("body", "")).strip()
        except Exception as exc:
            logging.exception("OpenAI prepare failed, using no-op fallback: %s", exc)
            excerpt = text.strip()
            if len(excerpt) > 900:
                excerpt = excerpt[:900] + "..."
            title = "Новость из отслеживаемого канала"
            body = excerpt

        if source_url:
            body = f"{body}\n\nИсточник: {source_url}"

        return PreparedPost(title=title, body=body)
