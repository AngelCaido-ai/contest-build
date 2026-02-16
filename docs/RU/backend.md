# Модуль backend

REST API на **FastAPI** с PostgreSQL (SQLAlchemy ORM), escrow-интеграцией с блокчейном TON, Telegram-уведомлениями и фоновыми задачами через Redis + RQ.

## Table of Contents

- [Структура](#структура)
- [Конфигурация](#конфигурация-coreconfigpy)
- [Авторизация и безопасность](#авторизация-и-безопасность)
- [Модели данных](#модели-данных)
- [Статусы сделки (DealStatus)](#статусы-сделки-dealstatus)
- [API-эндпоинты](#api-эндпоинты)
- [Сервисы](#сервисы)
- [Фоновые задачи](#фоновые-задачи-tasksdeal_taskspy)
- [Worker](#worker)
- [Escrow-флоу](#escrow-флоу-полный-цикл)
- [Миграции (Alembic)](#миграции-alembic)
- [Запуск](#запуск)
- [Стек технологий](#стек-технологий)

## Структура

```
backend/
├── __init__.py
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
│       ├── 0001_initial.py
│       ├── 0002_escrow_fields.py
│       ├── 0003_escrow_comment.py
│       ├── 0004_deal_brief.py
│       ├── 0005_user_tg_username.py
│       └── 0006_sweep_fields.py
├── app/
│   ├── __init__.py
│   ├── main.py                    # Точка входа FastAPI
│   ├── queue.py                   # Redis-очередь (RQ)
│   ├── api/
│   │   ├── deps.py                # Зависимости: get_db, get_current_user, get_bot_secret
│   │   └── routes/
│   │       ├── auth.py            # Авторизация (miniapp, bot)
│   │       ├── bot_actions.py     # Действия бота (upsert, deals, creative, tamper, ...)
│   │       ├── health.py          # Health check (DB + Redis)
│   │       ├── channels.py        # CRUD каналов и менеджеров
│   │       ├── deals.py           # CRUD сделок (miniapp)
│   │       ├── escrow.py          # Escrow: deposit
│   │       ├── listings.py        # CRUD листингов
│   │       ├── requests.py        # CRUD заявок
│   │       └── stats.py           # Статистика каналов
│   ├── core/
│   │   ├── config.py              # Settings (pydantic-settings)
│   │   ├── rate_limit.py          # Rate limiting (slowapi + Redis)
│   │   └── security.py            # JWT, verify_init_data
│   ├── db/
│   │   ├── base.py                # DeclarativeBase
│   │   └── session.py             # SessionLocal (sessionmaker)
│   ├── models/
│   │   ├── enums.py               # DealStatus, CreativeStatus
│   │   ├── user.py                # User
│   │   ├── channel.py             # Channel
│   │   ├── channel_manager.py     # ChannelManager
│   │   ├── channel_stats.py       # ChannelStats
│   │   ├── listing.py             # Listing
│   │   ├── request.py             # Request
│   │   ├── deal.py                # Deal
│   │   ├── deal_event.py          # DealEvent
│   │   ├── escrow_payment.py      # EscrowPayment
│   │   └── creative.py            # Creative
│   ├── schemas/                   # Pydantic-схемы (request/response)
│   │   ├── auth.py
│   │   ├── bot.py
│   │   ├── channel.py
│   │   ├── channel_stats.py
│   │   ├── creative.py
│   │   ├── deal.py
│   │   ├── escrow.py
│   │   ├── event.py
│   │   ├── listing.py
│   │   ├── request.py
│   │   └── user.py
│   ├── services/
│   │   ├── deal_actions.py        # Shared бизнес-логика сделок (constants, helpers, do_* операции)
│   │   ├── deal_service.py        # Переходы статусов, логирование событий
│   │   ├── escrow_service.py      # Создание депозита, подтверждение, release, refund
│   │   ├── stats_service.py       # MTProto + Bot API (fallback) статистика
│   │   ├── telegram_service.py    # Отправка сообщений/медиа через Bot API
│   │   └── ton_escrow.py          # TON-блокчейн: кошельки, транзакции, шифрование
│   └── tasks/
│       └── deal_tasks.py          # Фоновые задачи (таймауты, сканирование, постинг, верификация)
├── worker/
│   ├── __init__.py
│   ├── __main__.py                # RQ worker (SimpleWorker/WindowsWorker)
│   └── scheduler.py               # Планировщик задач (цикл каждые 20 сек)
├── scripts/
│   └── check_migrations_and_crud.py
└── tests/
    ├── test_deal_service.py
    ├── test_escrow_service.py
    ├── test_refund_api.py
    ├── test_ton_escrow.py
    └── test_ton_integration.py
```

---

## Конфигурация (`core/config.py`)

Класс `Settings` (pydantic-settings), читает `.env`:

| Переменная | Тип | По умолчанию | Назначение |
|---|---|---|---|
| `APP_NAME` | `str` | `contest` | Название приложения |
| `DATABASE_URL` | `str` | `postgresql+psycopg2://...` | Строка подключения к PostgreSQL |
| `REDIS_URL` | `str` | `redis://localhost:6379/0` | Строка подключения к Redis |
| `BOT_TOKEN` | `str` | `""` | Токен Telegram-бота |
| `BOT_SECRET` | `str` | **обязательный** | Shared secret для авторизации бота |
| `JWT_SECRET` | `str` | **обязательный, min 32 символа** | Секрет для JWT-токенов |
| `JWT_TTL_MINUTES` | `int` | `1440` | Время жизни JWT (24 часа) |
| `TELETHON_API_ID` | `int?` | `None` | API ID для MTProto (Telethon) |
| `TELETHON_API_HASH` | `str?` | `None` | API Hash для MTProto |
| `TELETHON_SESSION` | `str?` | `None` | Файл сессии Telethon |
| `TON_HOT_WALLET` | `str?` | `None` | Мнемоника горячего кошелька TON |
| `TON_API_KEY` | `str?` | `None` | API-ключ toncenter |
| `TON_NETWORK` | `str` | `mainnet` | Сеть TON (`mainnet` / `testnet`) |
| `TON_API_URL` | `str` | `https://toncenter.com/api/v2` | Базовый URL toncenter |
| `TON_API_TIMEOUT_SECONDS` | `int` | `10` | Таймаут запросов к toncenter |
| `TON_WALLET_VERSION` | `str?` | `None` | Версия кошелька (`v4r2`, `v5r1`, ...) |
| `TON_WALLET_ID` | `int?` | `None` | Wallet ID для V5 |
| `TON_WALLET_SUBWALLET` | `int?` | `None` | Subwallet для V5 |
| `TON_RESERVE_TON` | `float` | `0.02` | Резерв TON на комиссии |
| `TON_DEPOSIT_COMMENT_PREFIX` | `str` | `deal` | Префикс комментария в депозите |
| `ESCROW_SECRET_KEY` | `str?` | `None` | AES-ключ шифрования deposit_key |
| `BOT_LOG_CHAT_ID` | `int?` | `None` | Chat ID для проверки удалённых постов |
| `PAYMENT_TIMEOUT_MINUTES` | `int` | `1440` | Таймаут ожидания оплаты (24 часа) |
| `VERIFICATION_WINDOW_MINUTES` | `int` | `60` | Окно верификации поста (60 мин) |
| `SWEEP_DELAY_MINUTES` | `int` | `5` | Задержка перед sweep после release/refund |
| `SWEEP_MIN_BALANCE_TON` | `float` | `0.005` | Минимальный баланс для sweep (если меньше — комиссия съест всё) |
| `RATE_LIMIT_ESCROW_DEPOSIT` | `str` | `10/minute` | Лимит для `POST /escrow/deals/{id}/deposit` (ключ `user_id` из JWT) |
| `RATE_LIMIT_ESCROW_BOT` | `str` | `20/minute` | Лимит для escrow bot-only эндпоинтов и `POST /bot/deals/{id}/deposit` (ключ IP) |
| `INIT_DATA_MAX_AGE_SECONDS` | `int` | `300` | Максимальный возраст `auth_date` в Telegram `init_data` (защита от replay attack) |

---

## Авторизация и безопасность

### JWT

- Алгоритм: **HS256**
- Payload: `sub` (user_id), `iat`, `exp`
- Время жизни: `JWT_TTL_MINUTES` (по умолчанию 24 часа)
- Передаётся в заголовке: `Authorization: Bearer <token>`

### Два способа авторизации

| Эндпоинт | Метод | Кто вызывает | Механизм |
|---|---|---|---|
| `POST /auth/miniapp` | Web App | Mini App (фронтенд) | Валидация `init_data` (HMAC SHA-256 через `bot_token`) |
| `POST /auth/bot` | Bot API | Telegram-бот | Заголовок `X-Bot-Secret` |

При первой авторизации пользователь создаётся автоматически с ролью `advertiser`.

### Защита эндпоинтов бота

Все роуты `/bot/*` защищены зависимостью `get_bot_secret` — проверка заголовка `X-Bot-Secret`.

### Защита от replay attack (auth_date)

`verify_init_data` после проверки HMAC-подписи валидирует поле `auth_date` из `init_data`:
- Если `auth_date` отсутствует или не является числом — данные отклоняются.
- Если разница между текущим временем и `auth_date` превышает `INIT_DATA_MAX_AGE_SECONDS` (по умолчанию 300 сек / 5 мин) — данные отклоняются.
- Перехваченная строка `init_data` не может быть переиспользована после истечения окна.

### Timing-safe сравнение секретов

Все сравнения секретных значений выполняются через `hmac.compare_digest()` (constant-time), что исключает timing attack:
- `deps.py` — сравнение `X-Bot-Secret` с `settings.bot_secret`
- `security.py` — сравнение вычисленного HMAC с `received_hash` при валидации Telegram `init_data`

### Rate limiting финансовых эндпоинтов

- Реализован через `slowapi` с Redis storage (`REDIS_URL`)
- `POST /escrow/deals/{id}/deposit` — лимит `RATE_LIMIT_ESCROW_DEPOSIT`, ключ: `user_id` из JWT
- `POST /bot/deals/{id}/deposit` — лимит `RATE_LIMIT_ESCROW_BOT`, ключ: IP
- При превышении лимита API возвращает `429 Too Many Requests`

### Валидация TON-адресов

- `POST /auth/me/wallet` и `POST /bot/users/{tg_user_id}/wallet` — поле `linked_wallet` валидируется как TON-адрес.
- При невалидном формате API возвращает `422 Unprocessable Entity`, транзакция не отправляется.

### CORS

Middleware `CORSMiddleware` настроен с явными ограничениями:

| Параметр | Значение |
|---|---|
| `allow_origins` | Только из `CORS_ORIGINS` env (через запятую). Localhost **не** добавляется автоматически — для dev нужно указывать в `.env` |
| `allow_credentials` | `True` |
| `allow_methods` | `GET`, `POST`, `PATCH`, `DELETE`, `OPTIONS` |
| `allow_headers` | `Authorization`, `Content-Type`, `X-Bot-Secret` |

---

## Модели данных

### User
| Поле | Тип | Описание |
|---|---|---|
| `id` | `int` PK | ID пользователя |
| `tg_user_id` | `bigint` UNIQUE | Telegram user ID |
| `tg_username` | `str?` UNIQUE | Telegram username (нормализованный, без @) |
| `roles` | `JSON` | Список ролей (`["advertiser"]`, `["owner"]`, ...) |
| `linked_wallet` | `str?` | Привязанный TON-кошелёк |
| `created_at` | `datetime` | Дата создания |

### Channel
| Поле | Тип | Описание |
|---|---|---|
| `id` | `int` PK | ID канала |
| `tg_chat_id` | `bigint` UNIQUE | Telegram chat ID |
| `username` | `str?` | Username канала |
| `title` | `str?` | Название канала |
| `owner_user_id` | `int` FK → users | Владелец |
| `bot_admin_status` | `bool` | Бот — админ канала |
| `rights_snapshot` | `JSON?` | Снимок прав бота |
| `created_at` | `datetime` | Дата создания |

### ChannelManager
| Поле | Тип | Описание |
|---|---|---|
| `id` | `int` PK | ID записи |
| `channel_id` | `int` FK → channels | Канал |
| `user_id` | `int` FK → users | Менеджер |
| `permissions` | `JSON?` | Права менеджера |

### ChannelStats
| Поле | Тип | Описание |
|---|---|---|
| `id` | `int` PK | ID записи |
| `channel_id` | `int` FK → channels UNIQUE | Канал |
| `subscribers` | `int?` | Подписчики |
| `views_per_post` | `int?` | Просмотры на пост |
| `languages_json` | `JSON?` | Распределение языков |
| `premium_json` | `JSON?` | Доля premium-подписчиков |
| `updated_at` | `datetime` | Последнее обновление |
| `source` | `str?` | Источник данных (`mtproto` / `bot_api`) |

### Listing
| Поле | Тип | Описание |
|---|---|---|
| `id` | `int` PK | ID листинга |
| `channel_id` | `int` FK → channels | Канал |
| `price_ton` | `Numeric(18,8)?` | Цена в TON |
| `price_usd` | `Numeric(18,2)?` | Цена в USD |
| `format` | `str` | Формат размещения (по умолчанию `post`) |
| `categories` | `JSON?` | Категории |
| `constraints` | `JSON?` | Ограничения |
| `active` | `bool` | Активен ли листинг |
| `created_at` | `datetime` | Дата создания |

### Request
| Поле | Тип | Описание |
|---|---|---|
| `id` | `int` PK | ID заявки |
| `advertiser_id` | `int` FK → users | Рекламодатель |
| `budget` | `Numeric(18,2)?` | Бюджет |
| `niche` | `str?` | Тематика |
| `languages` | `JSON?` | Языки |
| `min_subs` | `int?` | Мин. подписчики |
| `min_views` | `int?` | Мин. просмотры |
| `dates` | `JSON?` | Даты размещения |
| `brief` | `text?` | Бриф |
| `created_at` | `datetime` | Дата создания |

### Deal
| Поле | Тип | Описание |
|---|---|---|
| `id` | `int` PK | ID сделки |
| `listing_id` | `int?` FK → listings | Листинг-источник |
| `request_id` | `int?` FK → requests | Заявка-источник |
| `advertiser_id` | `int` FK → users | Рекламодатель |
| `channel_id` | `int` FK → channels | Канал |
| `price` | `Numeric(18,2)?` | Цена сделки |
| `format` | `str?` | Формат |
| `brief` | `text?` | Бриф |
| `publish_at` | `datetime?` | Дата публикации |
| `verification_window` | `int?` | Окно верификации (мин) |
| `status` | `DealStatus` | Статус сделки |
| `posted_message_id` | `bigint?` | ID опубликованного сообщения |
| `posted_at` | `datetime?` | Дата публикации |
| `verification_started_at` | `datetime?` | Начало верификации |
| `tampered` | `bool` | Пост был изменён |
| `deleted` | `bool` | Пост был удалён |
| `created_at` | `datetime` | Дата создания |
| `updated_at` | `datetime` | Дата обновления |

### EscrowPayment
| Поле | Тип | Описание |
|---|---|---|
| `id` | `int` PK | ID записи |
| `deal_id` | `int` FK → deals UNIQUE | Сделка |
| `deposit_address` | `str` | Адрес депозита |
| `deposit_comment` | `str?` | Комментарий к транзакции |
| `deposit_key` | `str?` | Зашифрованная мнемоника |
| `expected_amount` | `Numeric(18,8)?` | Ожидаемая сумма |
| `tx_hash` | `str?` | Хеш входящей транзакции |
| `confirmed_at` | `datetime?` | Подтверждение оплаты |
| `release_tx_hash` | `str?` | Хеш транзакции release |
| `refund_tx_hash` | `str?` | Хеш транзакции refund |
| `sweep_tx_hash` | `str?` | Хеш транзакции sweep (или маркер skip) |
| `payout_address` | `str?` | Адрес выплаты (owner) |
| `refund_address` | `str?` | Адрес возврата (advertiser) |
| `released_at` | `datetime?` | Дата выплаты |
| `refunded_at` | `datetime?` | Дата возврата |
| `swept_at` | `datetime?` | Дата sweep остатка |
| `created_at` | `datetime` | Дата создания |

### Creative
| Поле | Тип | Описание |
|---|---|---|
| `id` | `int` PK | ID креатива |
| `deal_id` | `int` FK → deals | Сделка |
| `text` | `text?` | Текст поста |
| `media_file_ids` | `JSON?` | Медиафайлы (file_id) |
| `version` | `int` | Версия (инкрементная) |
| `status` | `CreativeStatus` | Статус (`DRAFT`, `REVIEW`, `APPROVED`) |
| `created_at` | `datetime` | Дата создания |

### DealEvent
| Поле | Тип | Описание |
|---|---|---|
| `id` | `int` PK | ID события |
| `deal_id` | `int` FK → deals | Сделка |
| `type` | `str` | Тип события |
| `payload` | `JSON?` | Дополнительные данные |
| `created_at` | `datetime` | Дата создания |

---

## Статусы сделки (DealStatus)

```
NEGOTIATING → TERMS_LOCKED → AWAITING_PAYMENT → FUNDED →
CREATIVE_DRAFT → CREATIVE_REVIEW → APPROVED →
SCHEDULED → POSTED → VERIFYING → RELEASED
                                            ↘ REFUNDED
Любой статус (кроме POSTED/VERIFYING/RELEASED/REFUNDED) → CANCELED
```

### Допустимые переходы

`set_status` enforce'ит эту таблицу — при недопустимом переходе бросает `InvalidTransitionError`.

| Из | В |
|---|---|
| `NEGOTIATING` | `TERMS_LOCKED`, `CANCELED` |
| `TERMS_LOCKED` | `TERMS_LOCKED`, `AWAITING_PAYMENT`, `CREATIVE_DRAFT`, `CANCELED` |
| `AWAITING_PAYMENT` | `FUNDED`, `CANCELED` |
| `FUNDED` | `CREATIVE_DRAFT`, `CREATIVE_REVIEW`, `CANCELED`, `REFUNDED` |
| `CREATIVE_DRAFT` | `CREATIVE_REVIEW`, `CANCELED` |
| `CREATIVE_REVIEW` | `APPROVED`, `CREATIVE_DRAFT`, `CREATIVE_REVIEW`, `CANCELED` |
| `APPROVED` | `SCHEDULED`, `POSTED`, `VERIFYING`, `CANCELED` |
| `SCHEDULED` | `POSTED`, `VERIFYING`, `CANCELED` |
| `POSTED` | `VERIFYING` |
| `VERIFYING` | `RELEASED`, `REFUNDED` |
| `RELEASED` | — (terminal) |
| `REFUNDED` | — (terminal) |
| `CANCELED` | — (terminal) |

### Роли и разрешённые переходы

| Роль | Может установить статусы |
|---|---|
| `owner` (владелец канала / менеджер) | `TERMS_LOCKED`, `CANCELED`, `SCHEDULED`, `POSTED`, `VERIFYING`, `RELEASED`, `REFUNDED` |
| `advertiser` (рекламодатель) | `AWAITING_PAYMENT`, `FUNDED`, `CANCELED` |

---

## API-эндпоинты

### Health (`/health`)

| Метод | Путь | Описание | Авторизация |
|---|---|---|---|
| `GET` | `/health` | Проверка здоровья сервиса (DB + Redis). 200 — всё ок, 503 — хотя бы один компонент недоступен | — |

### Auth (`/auth`)

| Метод | Путь | Описание |
|---|---|---|
| `POST` | `/auth/miniapp` | Авторизация через Telegram Web App `init_data` |
| `POST` | `/auth/bot` | Авторизация от бота (`X-Bot-Secret`) |
| `GET` | `/auth/me` | Текущий пользователь по JWT |
| `POST` | `/auth/me/wallet` | Обновить payout-кошелёк текущего пользователя (TON-адрес валидируется) |

### Channels (`/channels`)

| Метод | Путь | Описание | Авторизация |
|---|---|---|---|
| `POST` | `/channels/` | Создать канал | JWT |
| `GET` | `/channels/` | Список каналов текущего пользователя (owner + manager) | JWT |
| `GET` | `/channels/{id}` | Получить канал | JWT (owner/manager) |
| `PATCH` | `/channels/{id}` | Обновить канал | JWT (owner) |
| `POST` | `/channels/{id}/managers` | Добавить менеджера | JWT (owner) |
| `GET` | `/channels/{id}/managers` | Список менеджеров | JWT (owner) |
| `DELETE` | `/channels/{id}/managers/{mid}` | Удалить менеджера | JWT (owner) |

`GET /channels/` и `GET /channels/{id}` включают поле `stats` (если статистика для канала уже сохранена в `channel_stats`).

### Listings (`/listings`)

| Метод | Путь | Описание | Авторизация |
|---|---|---|---|
| `POST` | `/listings/` | Создать листинг | JWT (owner) |
| `GET` | `/listings/` | Список листингов (фильтры: `price_min`, `price_max`, `active`, `channel_id`, `exclude_own`; пагинация: `limit`, `offset`) | JWT |
| `GET` | `/listings/{id}` | Получить листинг (включает preview канала и статистику, если есть) | JWT |
| `PATCH` | `/listings/{id}` | Обновить листинг | JWT (owner) |

`GET /listings/{id}` дополнительно возвращает объект `channel` (id, username, title, stats) для предпросмотра в Mini App.

### Requests (`/requests`)

| Метод | Путь | Описание | Авторизация |
|---|---|---|---|
| `POST` | `/requests/` | Создать заявку | JWT |
| `GET` | `/requests/` | Список заявок (фильтры: `budget_min`, `budget_max`; пагинация: `limit`, `offset`) | JWT |
| `GET` | `/requests/{id}` | Получить заявку | JWT |
| `PATCH` | `/requests/{id}` | Обновить заявку | JWT (advertiser) |

### Deals (`/deals`)

| Метод | Путь | Описание | Авторизация |
|---|---|---|---|
| `POST` | `/deals/` | Создать сделку (из листинга или заявки); 409 с `deal_id` если уже есть активная сделка по листингу или по заявке+каналу | JWT |
| `GET` | `/deals/` | Список сделок текущего пользователя (пагинация: `limit`, `offset`) | JWT |
| `GET` | `/deals/{id}` | Получить сделку | JWT (участник) |
| `GET` | `/deals/{id}/events` | История событий сделки (новые первыми) | JWT (участник) |
| `POST` | `/deals/{id}/terms` | Зафиксировать условия сделки | JWT (owner/manager) |
| `POST` | `/deals/{id}/publish_at` | Установить publish_at | JWT (owner/manager) |
| `POST` | `/deals/{id}/status` | Изменить статус сделки | JWT (зависит от роли и переходов) |
| `POST` | `/deals/{id}/creative` | Отправить креатив | JWT (owner/manager) |
| `GET` | `/deals/{id}/creative` | Получить креатив (последний или по `version`) | JWT (участник) |
| `POST` | `/deals/{id}/creative/status` | Ревью креатива (APPROVED/DRAFT) | JWT (advertiser) |
| `POST` | `/deals/{id}/advertiser_brief` | Отправить бриф рекламодателя (text/media/publish_at) | JWT (advertiser) |
| `POST` | `/deals/media/upload` | Загрузить файл в Telegram и получить `file_id` для media_file_ids | JWT |

`GET /deals/{id}` возвращает расширенный объект (поверх базовой схемы сделки), чтобы Mini App мог показать больше контекста без дополнительных запросов.

| Поле | Тип | Описание |
|---|---|---|
| `channel_info` | `object \| null` | Краткая информация о канале + статистика (если сохранена в `channel_stats`) |
| `advertiser_info` | `object \| null` | Краткая информация о рекламодателе |
| `events` | `DealEventOut[]` | История событий сделки (отсортирована по `created_at`) |

### Escrow (`/escrow`)

| Метод | Путь | Описание | Авторизация |
|---|---|---|---|
| `POST` | `/escrow/deals/{id}/deposit` | Создать депозитный адрес | JWT (участник) |

Эндпоинты confirm, release, refund удалены — worker вызывает сервисные функции `escrow_service` напрямую, минуя HTTP.

### Stats (`/stats`)

| Метод | Путь | Описание | Авторизация |
|---|---|---|---|
| `POST` | `/stats/channels/{id}/refresh` | Обновить статистику канала | JWT (owner/manager) |

### Bot Actions (`/bot`)

Все эндпоинты защищены заголовком `X-Bot-Secret`.

| Метод | Путь | Описание |
|---|---|---|
| `POST` | `/bot/users/upsert` | Создать/обновить пользователя |
| `POST` | `/bot/users/{tg_user_id}/wallet` | Привязать кошелёк (TON-адрес валидируется) |
| `POST` | `/bot/channels` | Создать/обновить канал |
| `GET` | `/bot/channels` | Список каналов пользователя (по `tg_user_id`) |
| `POST` | `/bot/listings` | Создать листинг (требуется `linked_wallet`, иначе 400) |
| `GET` | `/bot/listings` | Список листингов (фильтры: `price_min`, `price_max`, `active`, `channel_id`; пагинация: `limit`, `offset`) |
| `GET` | `/bot/listings/{id}` | Получить листинг |
| `POST` | `/bot/requests` | Создать заявку |
| `GET` | `/bot/requests` | Список заявок (фильтры: `budget_min`, `budget_max`; пагинация: `limit`, `offset`) |
| `GET` | `/bot/requests/{id}` | Получить заявку |
| `POST` | `/bot/deals` | Создать сделку; 409 если по листингу уже есть активная сделка |
| `GET` | `/bot/deals` | Список сделок (фильтры: `tg_user_id`, `statuses`, `role`, `channel_id`, `limit`, `offset`, `order_by`) |
| `GET` | `/bot/deals/{id}` | Получить сделку |
| `POST` | `/bot/deals/{id}/terms` | Зафиксировать условия сделки |
| `POST` | `/bot/deals/{id}/publish_at` | Установить дату публикации |
| `POST` | `/bot/deals/{id}/status` | Изменить статус сделки |
| `POST` | `/bot/deals/{id}/deposit` | Создать депозит |
| `POST` | `/bot/deals/{id}/creative` | Создать/отправить креатив |
| `POST` | `/bot/deals/{id}/creative/status` | Обновить статус креатива (approve/reject) |
| `GET` | `/bot/deals/{id}/creative` | Получить креатив (последний или по версии) |
| `POST` | `/bot/deals/{id}/messages` | Отправить сообщение по сделке (text/media) |
| `GET` | `/bot/deals/{id}/messages` | Получить историю сообщений по сделке |
| `POST` | `/bot/deals/{id}/advertiser_brief` | Бриф рекламодателя с медиа и пожеланием publish_at |
| `POST` | `/bot/deals/{id}/events` | Добавить событие сделки |
| `POST` | `/bot/tamper` | Отметить пост как изменённый |
| `POST` | `/bot/deleted` | Отметить пост как удалённый |

---

## Сервисы

### deal_actions.py

Shared service layer для бизнес-логики сделок. Извлечён из `deals.py` и `bot_actions.py` для устранения дублирования (~750 строк). Route handlers делегируют в `do_*` функции, которые принимают `user_id: int` (не `User` и не `tg_user_id`), бросают `ValueError` при доменных ошибках и `InvalidTransitionError` при недопустимых переходах статуса.

**Константы:**
- `ROLE_OWNER`, `ROLE_ADVERTISER` — строковые идентификаторы ролей
- `ROLE_ALLOWED_STATUSES` — какие статусы может устанавливать каждая роль
- `FINAL_DEAL_STATUSES` — терминальные статусы (`RELEASED`, `REFUNDED`, `CANCELED`)

**Helpers:**
- `get_deal_role_flags(db, deal, user_id)` → `(is_owner, is_advertiser)` — определение роли по `user_id`; raises `ValueError("channel_not_found")`, `ValueError("not_deal_participant")`
- `get_deal_role(db, deal, user_id)` → `str` — возвращает `ROLE_OWNER` или `ROLE_ADVERTISER`
- `next_step_for_role(status, role)` → подсказка следующего шага для уведомлений
- `format_deal_terms(deal)` → форматирование условий сделки
- `deal_action_keyboard(deal, role)` → inline-клавиатура для Telegram-уведомлений
- `send_deal_notification(deal, user, role, text)` → отправка уведомления с подсказкой и клавиатурой
- `notify_deal_parties(db, deal, text)` → уведомление обеих сторон
- `send_creative_to_advertiser(deal, creative, advertiser)` → отправка креатива рекламодателю

**Бизнес-операции:**
- `do_update_terms(db, deal_id, actor_user_id, fields)` → `Deal` — фиксация условий
- `do_update_publish_at(db, deal_id, actor_user_id, publish_at)` → `Deal` — установка даты публикации
- `do_update_status(db, deal_id, actor_user_id, new_status)` → `Deal` — изменение статуса
- `do_create_creative(db, deal_id, actor_user_id, text, media_file_ids)` → `Creative` — создание креатива
- `do_get_creative(db, deal_id, actor_user_id, version)` → `Creative` — получение креатива
- `do_update_creative_status(db, deal_id, actor_user_id, new_status, comment, publish_at)` → `Creative` — ревью креатива
- `do_add_advertiser_brief(db, deal_id, actor_user_id, text, media_file_ids, publish_at)` → `DealEvent` — бриф рекламодателя

### deal_service.py

- `InvalidTransitionError(ValueError)` — исключение при недопустимом переходе статуса; содержит `deal_id`, `current`, `target`
- `can_transition(current, new_status)` — проверка допустимости перехода (для UI hints)
- `set_status(deal, new_status)` — установка нового статуса с enforce'ом допустимых переходов; бросает `InvalidTransitionError` при переходе, отсутствующем в `ALLOWED_TRANSITIONS`
- `log_event(db, deal_id, type, payload)` — запись DealEvent

### escrow_service.py

- `create_deposit(db, deal, expected_amount)` — генерация нового кошелька, шифрование ключа, создание EscrowPayment, переход в `AWAITING_PAYMENT`
- `confirm_payment(db, deal, payment, tx_hash)` — подтверждение оплаты, переход в `FUNDED`
- `scan_incoming_payments(db)` — сканирование всех ожидающих депозитов, автоподтверждение при обнаружении транзакции
- `release_payment(db, deal, payout_address)` — отправка средств владельцу канала, переход в `RELEASED`
- `refund_payment(db, deal, refund_address, reason)` — возврат средств рекламодателю, переход в `REFUNDED`
- `sweep_deposit(db, deal, payment)` — возврат остатка (reserve) с deposit-кошелька рекламодателю (mode 128)

**Защита от race condition (пессимистичная блокировка):**
Все финансовые операции (`confirm_payment`, `release_payment`, `refund_payment`, `sweep_deposit`) выполняют `SELECT ... FOR UPDATE` на строках `Deal` и `EscrowPayment` перед проверкой идемпотентности. Это предотвращает двойную отправку TON при конкурентных запросах от нескольких worker/API-запросов. `scan_incoming_payments` блокирует строку только после обнаружения транзакции в блокчейне, чтобы не держать lock на время HTTP-запроса. `create_deposit_address` в routes/escrow.py аналогично блокирует строку Deal перед проверкой существующего payment. Фоновые задачи `check_verification_windows` и `sweep_completed_deposits` перечитывают deal+payment с блокировкой в цикле перед вызовом финансовых функций.

### ton_escrow.py

Интеграция с блокчейном TON через toncenter API (v2 + v3):

- `create_deposit_wallet(deal_id)` — генерация нового TON-кошелька (v4r2)
- `encrypt_deposit_key(key)` / `decrypt_deposit_key(value)` — AES-GCM шифрование мнемоники; `decrypt_deposit_key` бросает `ValueError` при любой ошибке дешифровки (невалидные данные, неверный ключ, повреждённый blob)
- `build_deposit_comment(deal_id)` — формирование комментария `deal:<id>`
- `find_incoming_tx(address, amount, comment)` — поиск входящей транзакции по адресу/сумме/комментарию
- `send_payout(key, address, amount)` — отправка TON на адрес выплаты
- `send_refund(key, address, amount)` — отправка TON на адрес возврата
- `send_sweep(key, address)` — отправка всего остатка на адрес рекламодателя (mode 128)
- Поддержка кошельков: v1r1–v4r2, v5r1 (автоопределение версии)
- Fallback: v3 API → v2 API при ошибках
- Retry: до 3 попыток при transient-ошибках

### stats_service.py

- `fetch_stats(chat_id)` — получение статистики канала через MTProto (Telethon, `GetBroadcastStatsRequest`)
- `fetch_bot_api_subscribers(chat_id)` — fallback: количество подписчиков через Bot API

### telegram_service.py

Все HTTP-запросы к Telegram Bot API выполняются через `requests.Session` с автоматическим retry:
- До **3 повторных попыток** при transient-ошибках (429, 500, 502, 503, 504)
- **Exponential backoff**: 1 с → 2 с → 4 с между попытками
- При `429 Too Many Requests` учитывается заголовок `Retry-After` от Telegram
- Таймауты: 30 с для обычных запросов, 60 с для загрузки файлов

Функции:

- `send_message(chat_id, text, reply_markup)` — отправка текстового сообщения
- `send_media(chat_id, text, media_items)` — отправка медиа (photo/video/document/animation, группа или одиночное)
- `upload_media_for_user(chat_id, filename, content, content_type)` — загрузка файла в Telegram и получение `file_id`
- `copy_message(from_chat_id, message_id, to_chat_id)` — копирование сообщения (для проверки удалённых постов)
- `get_chat_administrators(chat_id)` — получение списка администраторов чата
- `is_chat_admin(chat_id, tg_user_id)` — проверка, является ли пользователь админом

---

## Фоновые задачи (`tasks/deal_tasks.py`)

Выполняются через RQ worker, планировщик ставит их в очередь каждые 20 секунд.

| Задача | Описание |
|---|---|
| `check_payment_timeouts` | Отмена сделок в статусе `AWAITING_PAYMENT`, если прошло больше `PAYMENT_TIMEOUT_MINUTES` |
| `scan_escrow_deposits` | Сканирование блокчейна на входящие транзакции для ожидающих депозитов |
| `process_scheduled_posts` | Публикация постов в каналы для сделок с `publish_at ≤ now` и статусом `APPROVED`/`SCHEDULED` |
| `check_deleted_posts` | Проверка удалённых постов через `copyMessage` в лог-чат |
| `check_verification_windows` | По истечении окна верификации: `release` если пост цел, `refund` если изменён/удалён |
| `sweep_completed_deposits` | Sweep остатков с deposit-кошельков после `RELEASED/REFUNDED` с задержкой `SWEEP_DELAY_MINUTES` |

---

## Worker

### `worker/__main__.py`

RQ worker (`SimpleWorker` с `TimerDeathPenalty` для Windows). Подключается к Redis, обрабатывает задачи из очереди.

### `worker/scheduler.py`

Бесконечный цикл, ставит 6 задач в очередь каждые 20 секунд с дедупликацией:

- Каждая задача ставится с `job_id=task.__name__` — в Redis максимум 1 job на тип задачи.
- Перед `enqueue` проверяется статус существующего job через `Job.fetch()`: если `queued`, `started` или `scheduled` — enqueue пропускается (лог на уровне DEBUG).
- `result_ttl=0` — результаты завершённых job не хранятся в Redis (задачи ничего не возвращают).
- `job_timeout` — зависшая задача убивается worker-ом, job_id освобождается для следующего цикла.

| Задача | `job_timeout` (сек) | Причина |
|---|---|---|
| `scan_escrow_deposits` | 120 | HTTP к TonCenter, сканирование платежей |
| `check_verification_windows` | 120 | HTTP к TonCenter, release/refund |
| `sweep_completed_deposits` | 120 | HTTP к TonCenter, sweep транзакции |
| `process_scheduled_posts` | 60 | Telegram API |
| `check_deleted_posts` | 60 | Telegram API |
| `check_payment_timeouts` | 30 | Только DB-операции |

```
scan_escrow_deposits → check_verification_windows → sweep_completed_deposits →
process_scheduled_posts → check_deleted_posts → check_payment_timeouts → sleep(20) → повтор
```

> Tamper detection выполняется отдельным watcher-ботом (см. [watcher.md](watcher.md)).

---

## Escrow-флоу (полный цикл)

```
1. Owner фиксирует условия          → TERMS_LOCKED
2. Advertiser запрашивает депозит    → создаётся TON-кошелёк, AWAITING_PAYMENT
3. Advertiser отправляет TON         → scan_escrow_deposits подтверждает, FUNDED
4. Owner создаёт креатив             → CREATIVE_REVIEW
5. Advertiser одобряет               → APPROVED
6. Owner назначает publish_at        → SCHEDULED
7. process_scheduled_posts публикует → VERIFYING
8a. Пост цел → check_verification_windows → release → RELEASED
8b. Пост изменён/удалён → refund → REFUNDED
```

---

## Миграции (Alembic)

| Миграция | Описание |
|---|---|
| `0001_initial` | Все таблицы: users, channels, channel_managers, channel_stats, listings, requests, deals, escrow_payments, creatives, deal_events |
| `0002_escrow_fields` | Добавлены поля `deposit_key`, `release_tx_hash`, `refund_tx_hash`, `payout_address`, `refund_address`, `released_at`, `refunded_at` |
| `0003_escrow_comment` | Добавлено поле `deposit_comment` |
| `0004_deal_brief` | Добавлено поле `brief` в deals |
| `0005_user_tg_username` | Добавлено поле `tg_username` в users |
| `0006_sweep_fields` | Добавлены поля `sweep_tx_hash`, `swept_at` для sweep остатков escrow |

---

## Запуск

```bash
# API сервер
uvicorn backend.app.main:app --reload

# Worker (обработка задач)
python -m backend.worker

# Планировщик (постановка задач в очередь)
python -m backend.worker.scheduler
```

---

## Стек технологий

| Компонент | Технология |
|---|---|
| Фреймворк | FastAPI |
| ORM | SQLAlchemy 2.0 (mapped_column) |
| БД | PostgreSQL |
| Миграции | Alembic |
| Очередь | Redis + RQ |
| JWT | python-jose |
| Блокчейн | TON (tonsdk, pytoniq) |
| Шифрование | cryptography (AES-GCM) |
| Telegram | requests (Bot API, retry через urllib3), Telethon (MTProto) |
| Валидация | Pydantic v2 + pydantic-settings |
