# ContentFactoryFT

Telegram-only бот для мониторинга выбранных каналов и репоста в ваш канал.

## Что умеет сейчас
- Забирает новые посты из `TG_SOURCE_CHANNELS`.
- Не тащит старую ленту при первом запуске (`START_MODE=now` по умолчанию).
- Делает редактуру/перевод через OpenAI (опционально) или fallback-эвристикой.
- Удаляет рекламные фрагменты.
- Для РФ-темы применяет политику `RUSSIA_POLICY=review|drop`.
- Отправляет спорные посты на модерацию в `ADMIN_REVIEW_CHAT_ID`.
- Поддерживает команды модератора `/pending`, `/approve <id>`, `/reject <id>`.
- Помечает обработанные сообщения в SQLite, чтобы не дублировать.

## Важно про настройки
`.env` содержит ключи. **Не коммитьте `.env` в git**.

## Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Заполните `.env`:
- `TG_API_ID` + `TG_API_HASH` (получить на `my.telegram.org` для чтения каналов),
- `TG_BOT_TOKEN` (бот для отправки),
- `TG_SOURCE_CHANNELS` (источники через запятую),
- `TG_TARGET_CHAT` (основной канал/чат),
- `ADMIN_REVIEW_CHAT_ID` (чат модерации, где работают команды),
- `RUSSIA_POLICY` (`review` или `drop`),
- `START_MODE` (`now` или `lookback`),
- `OPENAI_API_KEY` (необязательно).

Запуск:

```bash
PYTHONPATH=src python -m newsbot.main
```

## Команды модерации
Команды принимаются в `ADMIN_REVIEW_CHAT_ID`:
- `/pending` — список ожидающих.
- `/approve <id>` — опубликовать в `TG_TARGET_CHAT`.
- `/reject <id>` — отклонить.

## Файлы
- `src/newsbot/main.py` — основной polling pipeline + routing publish/review/drop.
- `src/newsbot/telegram_client.py` — чтение сообщений из Telegram-каналов.
- `src/newsbot/llm.py` — обработка контента (OpenAI + fallback).
- `src/newsbot/publisher.py` — отправка в Telegram Bot API + polling команд.
- `src/newsbot/state.py` — дедупликация, cursor'ы, очередь модерации (SQLite).
