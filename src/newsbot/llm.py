from __future__ import annotations

import json
import re
from dataclasses import dataclass

try:
    from openai import OpenAI
except ImportError:  # optional dependency at runtime
    OpenAI = None


RUSSIA_KEYWORDS = (
    "росси",
    "рф",
    "russia",
    "moscow",
    "москв",
)

ADS_PATTERNS = [
    r"подписыв(ай|айтесь)",
    r"реклама",
    r"промокод",
    r"скидк",
    r"заказать",
    r"купить",
    r"https?://[^\s]*ref[^\s]*",
]


@dataclass(frozen=True)
class PreparedPost:
    title: str
    body: str


@dataclass(frozen=True)
class ProcessedContent:
    topic: str
    has_personal_opinion: bool
    has_ads: bool
    action: str
    ru_text: str


class ContentProcessor:
    def prepare(self, text: str, source_url: str | None) -> PreparedPost:
        result = self.process_message(text)
        body = result.ru_text
        if source_url:
            body = f"{body}\n\nИсточник: {source_url}"
        return PreparedPost(title="Новость из отслеживаемого канала", body=body)

    def process_message(self, text: str) -> ProcessedContent:
        raise NotImplementedError


class NoOpContentProcessor(ContentProcessor):
    def process_message(self, text: str) -> ProcessedContent:
        cleaned = _strip_ads(text)
        topic = _topic_by_heuristics(cleaned)
        is_ru = _is_probably_russian(cleaned)
        action = "publish" if is_ru else "review"
        return ProcessedContent(
            topic=topic,
            has_personal_opinion=False,
            has_ads=cleaned != text,
            action=action,
            ru_text=cleaned.strip(),
        )


class OpenAIContentProcessor(ContentProcessor):
    def __init__(self, api_key: str, model: str) -> None:
        if OpenAI is None:
            raise RuntimeError("openai package is required for OpenAIContentProcessor")
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def process_message(self, text: str) -> ProcessedContent:
        prompt = (
            "Ты редактор новостей проекта 'Голос Хайфы'. Верни только JSON с полями: "
            "topic, has_personal_opinion, has_ads, action, ru_text. "
            "topic: israel|middle_east|russia|other. "
            "action: publish|review|drop. "
            "Если текст про Россию/РФ/отношения с РФ -> action=review. "
            "Удали рекламу/промо/реферальные вставки. "
            "Если есть личные мнения автора источника — убери их, оставь только факты. "
            "Для Израиля/Ближнего Востока стиль нейтрально-позитивный, человеческий, без аналитики. "
            "Всегда дай итоговый русский текст в ru_text."
        )

        response = self._client.responses.create(
            model=self._model,
            input=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
        )

        payload = json.loads(response.output_text)
        return ProcessedContent(
            topic=str(payload.get("topic", "other")),
            has_personal_opinion=bool(payload.get("has_personal_opinion", False)),
            has_ads=bool(payload.get("has_ads", False)),
            action=str(payload.get("action", "publish")),
            ru_text=str(payload.get("ru_text", "")).strip(),
        )


def _topic_by_heuristics(text: str) -> str:
    low = text.lower()
    if any(k in low for k in RUSSIA_KEYWORDS):
        return "russia"
    if any(k in low for k in ("израил", "israel", "haifa", "хайф")):
        return "israel"
    if any(k in low for k in ("iran", "syria", "leban", "палестин", "ближн")):
        return "middle_east"
    return "other"


def _strip_ads(text: str) -> str:
    cleaned = text
    for pattern in ADS_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _is_probably_russian(text: str) -> bool:
    cyr = sum(1 for c in text if "а" <= c.lower() <= "я")
    lat = sum(1 for c in text if "a" <= c.lower() <= "z")
    return cyr >= lat
