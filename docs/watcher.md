# Модуль watcher

Лёгкий Telegram-бот на **aiogram 3** для отслеживания правок постов в каналах (tamper detection).

## Зачем нужен отдельный бот

Telegram Bot API **не доставляет** `edited_channel_post` обновления боту, который сам отправил сообщение. Это задокументированное поведение: `channel_post` описывается как «new **incoming** channel post», а сообщения бота не считаются «incoming» для него самого.

Решение — **второй бот** (watcher), который:
1. Добавлен как администратор канала (наравне с основным ботом).
2. Получает `edited_channel_post` для **всех** сообщений в канале, включая отправленные основным ботом.
3. При обнаружении правки вызывает backend API (`POST /bot/tamper`) для пометки сделки.

## Структура

```
watcher/
├── __init__.py
├── app/
│   ├── __init__.py
│   ├── config.py       # Конфигурация (WatcherSettings)
│   ├── handlers.py     # Обработчики канальных обновлений
│   └── main.py         # Точка входа, polling
```

---

## Конфигурация (`config.py`)

Класс `WatcherSettings` (pydantic-settings):

| Переменная          | Тип   | По умолчанию            | Описание                        |
|---------------------|-------|-------------------------|---------------------------------|
| `WATCHER_BOT_TOKEN` | str   | —                       | Токен watcher Telegram-бота     |
| `API_BASE_URL`      | str   | `http://localhost:8000` | Базовый URL backend API         |
| `BOT_SECRET`        | str   | —                       | Секрет для заголовка X-Bot-Secret |

---

## Точка входа (`main.py`)

1. Создаёт `Bot` с `WATCHER_BOT_TOKEN`.
2. Подключает единственный роутер (`handlers.router`).
3. `allowed_updates`: `["edited_channel_post", "edited_message", "channel_post"]`.
4. Удаляет вебхук и запускает polling.

---

## Обработчики (`handlers.py`)

| Хендлер                  | Тип обновления          | Логика                                                |
|--------------------------|-------------------------|-------------------------------------------------------|
| `on_edited_channel_post` | `edited_channel_post`   | Вызывает `_handle_edit` → `POST /bot/tamper`          |
| `on_edited_message`      | `edited_message`        | То же (для групп, привязанных к каналу)               |
| `on_channel_post`        | `channel_post`          | Fallback: обрабатывает только если `edit_date` задан  |

Функция `_handle_edit`:
1. Определяет `channel_id` из `message.sender_chat.id` (приоритет) или `message.chat.id`.
2. Вызывает `POST /bot/tamper` с `{channel_tg_chat_id, message_id}`.

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
  depends_on:
    backend:
      condition: service_started
  command: python -m watcher.app.main
```

Если `WATCHER_BOT_TOKEN` не задан, сервис ожидает (аналогично основному боту).

---

## Настройка

1. Создать нового бота через [@BotFather](https://t.me/BotFather).
2. Добавить токен в `.env`: `WATCHER_BOT_TOKEN=...`.
3. Добавить watcher-бота как администратора в каждый канал, где нужен мониторинг.
4. Перезапустить `docker compose up --build`.

---

## Зависимости

- **aiogram 3** — Telegram Bot Framework
- **pydantic / pydantic-settings** — конфигурация
- **requests** — HTTP-клиент к backend
