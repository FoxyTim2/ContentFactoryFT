from __future__ import annotations

from dataclasses import dataclass
from openai import OpenAI


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
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def prepare(self, text: str, source_url: str | None) -> PreparedPost:
        prompt = (
            "Ты редактор новостей. Переведи текст на русский (если уже русский — оставь), "
            "слегка отредактируй для ясности без искажения фактов, и верни JSON формата "
            '{"title":"...","body":"..."}. Заголовок до 90 символов, тело до 1200 символов.'
        )

        response = self._client.responses.create(
            model=self._model,
            input=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
        )
        raw = response.output_text

        import json

        payload = json.loads(raw)
        body = payload.get("body", "").strip()
        if source_url:
            body = f"{body}\n\nИсточник: {source_url}"

        return PreparedPost(
            title=payload.get("title", "Новость"),
            body=body,
        )
