# Watcher Module

Telegram userbot on **Telethon** (MTProto) for monitoring post **edits** and **deletions** in channels.

## Table of Contents

- [Why a Separate Userbot](#why-a-separate-userbot)
- [Structure](#structure)
- [Configuration](#configuration-configpy)
- [Entry Point](#entry-point-mainpy)
- [Handlers](#handlers-handlerspy)
- [Docker](#docker)
- [Setup](#setup)
- [Dependencies](#dependencies)

## Why a Separate Userbot

Telegram Bot API has two limitations:
1. **Does not deliver** `edited_channel_post` updates to a bot that sent the message itself.
2. **Does not notify** about message deletions in channels — no such update type exists in Bot API.

Only MTProto API (Telethon) with a **user session** can receive `UpdateDeleteChannelMessages` events that Telegram sends when posts are deleted.

The solution is a **Telethon userbot** (watcher) that:
1. Connects to Telegram via MTProto using a user session.
2. Receives `events.MessageEdited` to track post edits.
3. Receives `events.MessageDeleted` to track post deletions.
4. On detecting an edit, calls `POST /bot/tamper`.
5. On detecting a deletion, calls `POST /bot/deleted`.

## Structure

```
watcher/
├── __init__.py
├── app/
│   ├── __init__.py
│   ├── config.py       # Configuration (WatcherSettings)
│   ├── handlers.py     # Telethon event handlers
│   └── main.py         # Entry point, TelegramClient
```

## Configuration (`config.py`)

Class `WatcherSettings` (pydantic-settings):

| Variable | Type | Default | Description |
|---|---|---|---|
| `TELETHON_API_ID` | int | — | Application API ID (from my.telegram.org) |
| `TELETHON_API_HASH` | str | — | Application API Hash |
| `TELETHON_SESSION` | str | — | User StringSession |
| `API_BASE_URL` | str | `http://localhost:8000` | Backend API base URL |
| `BOT_SECRET` | str | — | Secret for X-Bot-Secret header |

> Watcher uses the same `TELETHON_*` variables as `stats_service`. No separate session required.

## Entry Point (`main.py`)

1. Creates `TelegramClient` with `WATCHER_TELETHON_SESSION`.
2. Connects to Telegram via MTProto (`client.start()`).
3. Registers event handlers: `MessageEdited`, `MessageDeleted`.
4. Runs infinite event loop (`run_until_disconnected`).

## Handlers (`handlers.py`)

| Handler | Telethon Event | Logic |
|---|---|---|
| `on_message_edited` | `events.MessageEdited` | Filters channels only → `POST /bot/tamper` |
| `on_message_deleted` | `events.MessageDeleted` | For each deleted message_id → `POST /bot/deleted` |

Function `_call_api`:
1. Sends POST request to backend with `{channel_tg_chat_id, message_id}`.
2. On 404 (channel/deal not found) — logs debug and skips.
3. On other errors — logs exception.

## Docker

Service `watcher` in `docker-compose.yml`:

```yaml
watcher:
  build: .
  env_file: ./.env
  environment:
    API_BASE_URL: http://backend:8000
    BOT_SECRET: "${BOT_SECRET}"
    TELETHON_API_ID: "${TELETHON_API_ID}"
    TELETHON_API_HASH: "${TELETHON_API_HASH}"
    TELETHON_SESSION: "${TELETHON_SESSION}"
  depends_on:
    backend:
      condition: service_healthy
  command: python -m watcher.app.main
```

If `TELETHON_SESSION` is not set, the service waits (same as main bot).

## Setup

1. Generate session (if not yet): `python generate_session.py` (enter phone number and code).
2. Add variables to `.env` (same as for stats_service):
   ```
   TELETHON_API_ID=12345678
   TELETHON_API_HASH=abc123...
   TELETHON_SESSION=1BVtsO...
   ```
3. Ensure the user account is **subscribed** to the channels that need monitoring.
4. Restart: `docker compose up -d --build watcher`.

## Dependencies

- **Telethon 1.36** — MTProto client for Telegram
- **httpx** — async HTTP client to backend
- **pydantic / pydantic-settings** — configuration
