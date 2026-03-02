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


@dataclass(frozen=True)
class ModerationResult:
    action: str  # allow | review | block
    reason: str


class ContentModerator:
    _AD_PATTERNS = (
        r"\bскидк",
        r"\bпромокод",
        r"\bреклам",
        r"\bпартн[её]р",
        r"\bкупи",
        r"\bbuy\b",
        r"\breferral\b",
        r"\bподписывайт",
    )
    _SENSITIVE_PATTERNS = (
        r"\bненавист",
        r"\bоскорб",
        r"\bнасили",
        r"\bэкстрем",
    )

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini") -> None:
        self._model = model
        self._client = None
        if api_key and OpenAI is not None:
            self._client = OpenAI(api_key=api_key)

    def assess(self, text: str) -> ModerationResult:
        heuristic = self._heuristic_assess(text)
        llm_result = self._llm_assess(text)

        candidates = [heuristic]
        if llm_result:
            candidates.append(llm_result)

        if any(item.action == "block" for item in candidates):
            reason = "; ".join(item.reason for item in candidates if item.action == "block")
            return ModerationResult(action="block", reason=reason or "blocked")
        if any(item.action == "review" for item in candidates):
            reason = "; ".join(item.reason for item in candidates if item.action == "review")
            return ModerationResult(action="review", reason=reason or "needs review")
        return ModerationResult(action="allow", reason="ok")

    def _heuristic_assess(self, text: str) -> ModerationResult:
        lowered = text.lower()

        for pattern in self._AD_PATTERNS:
            if re.search(pattern, lowered):
                return ModerationResult("block", "heuristic: detected advertising/marketing")

        for pattern in self._SENSITIVE_PATTERNS:
            if re.search(pattern, lowered):
                return ModerationResult("review", "heuristic: detected sensitive content")

        if len(lowered.strip()) < 20:
            return ModerationResult("review", "heuristic: too short / unclear content")

        alpha = sum(ch.isalpha() for ch in lowered)
        if alpha and (sum(ch in "!?$%#@" for ch in lowered) / max(len(lowered), 1) > 0.08):
            return ModerationResult("review", "heuristic: noisy/unclear content")

        return ModerationResult("allow", "heuristic: ok")

    def _llm_assess(self, text: str) -> ModerationResult | None:
        if self._client is None:
            return None
        prompt = (
            "Ты модератор контента. Верни только JSON: "
            '{"action":"allow|review|block","reason":"..."}. '
            "block: реклама/маркетинг/промо. "
            "review: сомнительный смысл, токсичность, чувствительный или потенциально нарушающий контент. "
            "allow: обычная новостная информация."
        )
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0,
            )
            raw = (response.choices[0].message.content or "").strip()
            payload = OpenAIContentProcessor._parse_payload(raw)
            action = str(payload.get("action", "review")).strip().lower()
            if action not in {"allow", "review", "block"}:
                action = "review"
            reason = str(payload.get("reason", "llm moderation")).strip() or "llm moderation"
            return ModerationResult(action=action, reason=f"llm: {reason}")
        except Exception as exc:
            logging.warning("LLM moderation failed, using heuristic only: %s", exc)
            return None



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
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.2,
            )
            raw = (response.choices[0].message.content or "").strip()
            payload = self._parse_payload(raw)
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
