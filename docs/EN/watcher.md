# Watcher Module

Lightweight Telegram bot on **aiogram 3** for monitoring post edits in channels (tamper detection).

## Table of Contents

- [Why a Separate Bot](#why-a-separate-bot)
- [Structure](#structure)
- [Configuration](#configuration-configpy)
- [Entry Point](#entry-point-mainpy)
- [Handlers](#handlers-handlerspy)
- [Docker](#docker)
- [Setup](#setup)
- [Dependencies](#dependencies)

## Why a Separate Bot

Telegram Bot API **does not deliver** `edited_channel_post` updates to a bot that sent the message itself. This is documented behavior: `channel_post` is described as "new **incoming** channel post", and bot's own messages do not count as "incoming" for itself.

The solution is a **second bot** (watcher) that:
1. Is added as channel administrator (alongside the main bot).
2. Receives `edited_channel_post` for **all** messages in the channel, including those sent by the main bot.
3. On detecting an edit, calls backend API (`POST /bot/tamper`) to mark the deal.

## Structure

```
watcher/
├── __init__.py
├── app/
│   ├── __init__.py
│   ├── config.py       # Configuration (WatcherSettings)
│   ├── handlers.py     # Channel update handlers
│   └── main.py         # Entry point, polling
```

## Configuration (`config.py`)

Class `WatcherSettings` (pydantic-settings):

| Variable | Type | Default | Description |
|---|---|---|---|
| `WATCHER_BOT_TOKEN` | str | — | Watcher Telegram bot token |
| `API_BASE_URL` | str | `http://localhost:8000` | Backend API base URL |
| `BOT_SECRET` | str | — | Secret for X-Bot-Secret header |

## Entry Point (`main.py`)

1. Creates `Bot` with `WATCHER_BOT_TOKEN`.
2. Registers single router (`handlers.router`).
3. `allowed_updates`: `["edited_channel_post", "edited_message", "channel_post"]`.
4. Removes webhook and starts polling.

## Handlers (`handlers.py`)

| Handler | Update type | Logic |
|---|---|---|
| `on_edited_channel_post` | `edited_channel_post` | Calls `_handle_edit` → `POST /bot/tamper` |
| `on_edited_message` | `edited_message` | Same (for groups linked to channel) |
| `on_channel_post` | `channel_post` | Fallback: handles only if `edit_date` is set |

Function `_handle_edit`:
1. Resolves `channel_id` from `message.sender_chat.id` (priority) or `message.chat.id`.
2. Calls `POST /bot/tamper` with `{channel_tg_chat_id, message_id}`.

## Docker

Service `watcher` in `docker-compose.yml`:

```yaml
watcher:
  build: .
  env_file: ./.env
  environment:
    API_BASE_URL: http://backend:8000
    BOT_SECRET: "${BOT_SECRET}"
  depends_on:
    backend:
      condition: service_started
  command: python -m watcher.app.main
```

If `WATCHER_BOT_TOKEN` is not set, the service waits (same as main bot).

## Setup

1. Create a new bot via [@BotFather](https://t.me/BotFather).
2. Add token to `.env`: `WATCHER_BOT_TOKEN=...`.
3. Add watcher bot as administrator to each channel requiring monitoring.
4. Restart `docker compose up --build`.

## Dependencies

- **aiogram 3** — Telegram Bot Framework
- **pydantic / pydantic-settings** — configuration
- **requests** — HTTP client to backend
