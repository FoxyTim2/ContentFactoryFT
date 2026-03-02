# ContentFactoryFT

Telegram-only бот для мониторинга выбранных каналов и репоста в ваш канал:
- забирает новые посты из `TG_SOURCE_CHANNELS`,
- переводит и слегка редактирует текст через OpenAI (опционально),
- публикует в `TG_TARGET_CHAT`,
- помечает обработанные сообщения в SQLite, чтобы не дублировать.

## Быстрый старт

1. Установите зависимости.

**macOS / Linux (bash/zsh):**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows PowerShell:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Скопируйте настройки:

```bash
cp .env.example .env
```

3. Заполните `.env`:
- `TG_API_ID` + `TG_API_HASH` (получить на `my.telegram.org` для чтения каналов),
- `TG_BOT_TOKEN` (бот для отправки),
- `TG_SOURCE_CHANNELS` (источники через запятую),
- `TG_TARGET_CHAT` (ваш канал/чат),
- `OPENAI_API_KEY` (необязательно; без него будет пересылка без LLM-редактуры).
- `TG_REVIEW_CHAT` (необязательно, но рекомендуется; канал/чат для сообщений, отправленных на согласование модератором).

4. Запуск.

**macOS / Linux (bash/zsh):**
```bash
PYTHONPATH=src python -m newsbot.main
```

**Windows PowerShell:**
```powershell
$env:PYTHONPATH = "src"
python -m newsbot.main
```

## Файлы
- `src/newsbot/main.py` — основной polling pipeline.
- `src/newsbot/telegram_client.py` — чтение сообщений из Telegram-каналов.
- `src/newsbot/llm.py` — перевод/редактура контента (OpenAI + fallback).
- `src/newsbot/publisher.py` — отправка в Telegram Bot API.
- `src/newsbot/state.py` — дедупликация на SQLite.
- `NEWS_AUTOMATION_ARCHITECTURE.md` — краткая архитектура и roadmap.
