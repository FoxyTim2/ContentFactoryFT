from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re

try:
    from openai import OpenAI
except ImportError:  # optional dependency at runtime
    OpenAI = None


CTA_MARKERS = (
    "подпишись",
    "подписывайся",
    "подписаться",
    "переходи",
    "переходите",
    "жми",
    "жмите",
    "купить",
    "закажи",
    "закажите",
    "регистрируйся",
    "регистрация",
    "промокод",
    "скидка",
    "акция",
    "только сегодня",
)

AMBIGUOUS_PROMO_MARKERS = (
    "партнерский материал",
    "спонсор",
    "спецпроект",
    "реклама",
    "при поддержке",
)


@dataclass(frozen=True)
class ModerationDecision:
    is_marketing: bool
    reason: str


class LLMMarketingClassifier:
    def classify(self, text: str) -> ModerationDecision:
        raise NotImplementedError


class NoOpMarketingClassifier(LLMMarketingClassifier):
    def classify(self, text: str) -> ModerationDecision:
        return ModerationDecision(is_marketing=False, reason="llm_unavailable_default_not_marketing")


class OpenAIMarketingClassifier(LLMMarketingClassifier):
    def __init__(self, api_key: str, model: str) -> None:
        if OpenAI is None:
            raise RuntimeError("openai package is required for OpenAIMarketingClassifier")
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def classify(self, text: str) -> ModerationDecision:
        prompt = (
            "Определи, является ли текст рекламным/маркетинговым сообщением. "
            "Рекламным считать контент с явным продвижением товара, услуги, канала, "
            "призывами к покупке/подписке/регистрации или промо-выгодой. "
            "Верни строго JSON: {\"is_marketing\": true|false, \"reason\": \"...\"}."
        )
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )

        raw = (response.choices[0].message.content or "").strip()
        payload = _parse_json_object(raw)
        is_marketing = bool(payload.get("is_marketing", False))
        reason = str(payload.get("reason", "llm_classification")).strip() or "llm_classification"
        return ModerationDecision(is_marketing=is_marketing, reason=reason)


class MarketingModerator:
    def __init__(self, classifier: LLMMarketingClassifier | None = None) -> None:
        self._classifier = classifier or NoOpMarketingClassifier()

    def is_marketing(self, text: str) -> ModerationDecision:
        normalized = " ".join(text.lower().split())
        if not normalized:
            return ModerationDecision(is_marketing=False, reason="empty_text")

        if _has_direct_cta(normalized):
            return ModerationDecision(is_marketing=True, reason="fast_rules_cta")

        if _has_ambiguous_marker(normalized):
            try:
                return self._classifier.classify(text)
            except Exception as exc:
                logging.exception("LLM moderation failed, treating as non-marketing: %s", exc)
                return ModerationDecision(
                    is_marketing=False,
                    reason="llm_failed_default_not_marketing",
                )

        return ModerationDecision(is_marketing=False, reason="fast_rules_non_marketing")


def is_marketing(text: str, classifier: LLMMarketingClassifier | None = None) -> bool:
    return MarketingModerator(classifier=classifier).is_marketing(text).is_marketing


def _has_direct_cta(text: str) -> bool:
    return any(marker in text for marker in CTA_MARKERS)


def _has_ambiguous_marker(text: str) -> bool:
    return any(marker in text for marker in AMBIGUOUS_PROMO_MARKERS)


def _parse_json_object(raw: str) -> dict[str, object]:
    cleaned = raw.strip()
    if not cleaned:
        return {}

    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.S)
    if fence_match:
        cleaned = fence_match.group(1)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        object_match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if object_match:
            return json.loads(object_match.group(0))
        raise
