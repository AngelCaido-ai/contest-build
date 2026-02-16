# Модуль watcher

Телеграм userbot на **Telethon** (MTProto) для отслеживания **правок** и **удалений** постов в каналах.

## Table of Contents

- [Зачем нужен отдельный userbot](#зачем-нужен-отдельный-userbot)
- [Структура](#структура)
- [Конфигурация](#конфигурация-configpy)
- [Точка входа](#точка-входа-mainpy)
- [Обработчики](#обработчики-handlerspy)
- [Docker](#docker)
- [Настройка](#настройка)
- [Зависимости](#зависимости)

## Зачем нужен отдельный userbot

Telegram Bot API имеет два ограничения:
1. **Не доставляет** `edited_channel_post` боту, который сам отправил сообщение.
2. **Не уведомляет** об удалении сообщений в каналах — такого типа обновления в Bot API не существует.

Только MTProto API (Telethon) с **пользовательской сессией** может получать событие `UpdateDeleteChannelMessages`, которое Telegram отправляет при удалении постов.

Решение — **Telethon userbot** (watcher), который:
1. Подключается к Telegram по MTProto через пользовательскую сессию.
2. Получает `events.MessageEdited` для отслеживания правок.
3. Получает `events.MessageDeleted` для отслеживания удалений.
4. При обнаружении правки вызывает `POST /bot/tamper`.
5. При обнаружении удаления вызывает `POST /bot/deleted`.

## Структура

```
watcher/
├── __init__.py
├── app/
│   ├── __init__.py
│   ├── config.py       # Конфигурация (WatcherSettings)
│   ├── handlers.py     # Обработчики событий Telethon
│   └── main.py         # Точка входа, TelegramClient
```

---

## Конфигурация (`config.py`)

Класс `WatcherSettings` (pydantic-settings):

| Переменная          | Тип   | По умолчанию            | Описание                              |
|---------------------|-------|-------------------------|---------------------------------------|
| `TELETHON_API_ID`   | int   | —                       | API ID приложения (из my.telegram.org) |
| `TELETHON_API_HASH` | str   | —                       | API Hash приложения                    |
| `TELETHON_SESSION`  | str   | —                       | StringSession пользователя             |
| `API_BASE_URL`      | str   | `http://localhost:8000` | Базовый URL backend API                |
| `BOT_SECRET`        | str   | —                       | Секрет для заголовка X-Bot-Secret      |

> Watcher использует те же `TELETHON_*` переменные, что и `stats_service`. Отдельная сессия не требуется.

---

## Точка входа (`main.py`)

1. Создаёт `TelegramClient` с `WATCHER_TELETHON_SESSION`.
2. Подключается к Telegram по MTProto (`client.start()`).
3. Регистрирует event handlers: `MessageEdited`, `MessageDeleted`.
4. Запускает бесконечный цикл приёма событий (`run_until_disconnected`).

---

## Обработчики (`handlers.py`)

| Хендлер              | Событие Telethon        | Логика                                                    |
|----------------------|-------------------------|-----------------------------------------------------------|
| `on_message_edited`  | `events.MessageEdited`  | Фильтрует только каналы → `POST /bot/tamper`              |
| `on_message_deleted` | `events.MessageDeleted` | Для каждого удалённого message_id → `POST /bot/deleted`   |

Функция `_call_api`:
1. Отправляет POST-запрос к backend с `{channel_tg_chat_id, message_id}`.
2. При 404 (канал/сделка не найдены) — пишет debug-лог и пропускает.
3. При других ошибках — логирует exception.

---

## Docker

Сервис `watcher` в `docker-compose.yml`:

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

Если `TELETHON_SESSION` не задан, сервис ожидает (аналогично основному боту).

---

## Настройка

1. Сгенерировать сессию (если ещё нет): `python generate_session.py` (ввести номер телефона и код).
2. Добавить переменные в `.env` (те же, что для stats_service):
   ```
   TELETHON_API_ID=12345678
   TELETHON_API_HASH=abc123...
   TELETHON_SESSION=1BVtsO...
   ```
3. Убедиться, что пользовательский аккаунт **подписан** на каналы, которые нужно мониторить.
4. Перезапустить: `docker compose up -d --build watcher`.

---

## Зависимости

- **Telethon 1.36** — MTProto клиент для Telegram
- **httpx** — асинхронный HTTP-клиент к backend
- **pydantic / pydantic-settings** — конфигурация
