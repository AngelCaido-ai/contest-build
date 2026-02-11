# Модуль backend

REST API на **FastAPI** с PostgreSQL (SQLAlchemy ORM), escrow-интеграцией с блокчейном TON, Telegram-уведомлениями и фоновыми задачами через Redis + RQ.

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
│       └── 0005_user_tg_username.py
├── app/
│   ├── __init__.py
│   ├── main.py                    # Точка входа FastAPI
│   ├── queue.py                   # Redis-очередь (RQ)
│   ├── api/
│   │   ├── deps.py                # Зависимости: get_db, get_current_user, get_bot_secret
│   │   └── routes/
│   │       ├── auth.py            # Авторизация (miniapp, bot)
│   │       ├── bot_actions.py     # Действия бота (upsert, deals, creative, tamper, ...)
│   │       ├── channels.py        # CRUD каналов и менеджеров
│   │       ├── deals.py           # CRUD сделок (miniapp)
│   │       ├── escrow.py          # Escrow: deposit, confirm, release, refund
│   │       ├── listings.py        # CRUD листингов
│   │       ├── requests.py        # CRUD заявок
│   │       └── stats.py           # Статистика каналов
│   ├── core/
│   │   ├── config.py              # Settings (pydantic-settings)
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
| `BOT_SECRET` | `str` | `""` | Shared secret для авторизации бота |
| `JWT_SECRET` | `str` | `change_me` | Секрет для JWT-токенов |
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
| `payout_address` | `str?` | Адрес выплаты (owner) |
| `refund_address` | `str?` | Адрес возврата (advertiser) |
| `released_at` | `datetime?` | Дата выплаты |
| `refunded_at` | `datetime?` | Дата возврата |
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

| Из | В |
|---|---|
| `NEGOTIATING` | `TERMS_LOCKED`, `CANCELED` |
| `TERMS_LOCKED` | `AWAITING_PAYMENT`, `CREATIVE_DRAFT`, `CANCELED` |
| `AWAITING_PAYMENT` | `FUNDED`, `CANCELED` |
| `FUNDED` | `CREATIVE_DRAFT`, `CANCELED` |
| `CREATIVE_DRAFT` | `CREATIVE_REVIEW`, `CANCELED` |
| `CREATIVE_REVIEW` | `APPROVED`, `CANCELED` |
| `APPROVED` | `SCHEDULED`, `CANCELED` |
| `SCHEDULED` | `POSTED`, `CANCELED` |
| `POSTED` | `VERIFYING` |
| `VERIFYING` | `RELEASED`, `REFUNDED` |

### Роли и разрешённые переходы

| Роль | Может установить статусы |
|---|---|
| `owner` (владелец канала / менеджер) | `TERMS_LOCKED`, `CANCELED`, `SCHEDULED`, `POSTED`, `VERIFYING`, `RELEASED`, `REFUNDED` |
| `advertiser` (рекламодатель) | `AWAITING_PAYMENT`, `FUNDED`, `CANCELED` |

---

## API-эндпоинты

### Auth (`/auth`)

| Метод | Путь | Описание |
|---|---|---|
| `POST` | `/auth/miniapp` | Авторизация через Telegram Web App `init_data` |
| `POST` | `/auth/bot` | Авторизация от бота (`X-Bot-Secret`) |

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

### Listings (`/listings`)

| Метод | Путь | Описание | Авторизация |
|---|---|---|---|
| `POST` | `/listings/` | Создать листинг | JWT (owner) |
| `GET` | `/listings/` | Список листингов (фильтры: `price_min`, `price_max`, `active`, `channel_id`, `exclude_own`) | JWT при `exclude_own=true` |
| `GET` | `/listings/{id}` | Получить листинг (включает preview канала и статистику, если есть) | — |
| `PATCH` | `/listings/{id}` | Обновить листинг | JWT (owner) |

`GET /listings/{id}` дополнительно возвращает объект `channel` (id, username, title, stats) для предпросмотра в Mini App.

### Requests (`/requests`)

| Метод | Путь | Описание | Авторизация |
|---|---|---|---|
| `POST` | `/requests/` | Создать заявку | JWT |
| `GET` | `/requests/` | Список заявок (фильтры: `budget_min`, `budget_max`) | — |
| `GET` | `/requests/{id}` | Получить заявку | — |
| `PATCH` | `/requests/{id}` | Обновить заявку | JWT (advertiser) |

### Deals (`/deals`)

| Метод | Путь | Описание | Авторизация |
|---|---|---|---|
| `POST` | `/deals/` | Создать сделку (из листинга или заявки); 409 если по листингу уже есть активная сделка | JWT |
| `GET` | `/deals/` | Список сделок текущего пользователя | JWT |
| `GET` | `/deals/{id}` | Получить сделку | JWT (участник) |

### Escrow (`/escrow`)

| Метод | Путь | Описание | Авторизация |
|---|---|---|---|
| `POST` | `/escrow/deals/{id}/deposit` | Создать депозитный адрес | JWT (участник) |
| `POST` | `/escrow/deals/{id}/confirm` | Подтвердить оплату | `X-Bot-Secret` |
| `POST` | `/escrow/deals/{id}/release` | Выплата владельцу | `X-Bot-Secret` |
| `POST` | `/escrow/deals/{id}/refund` | Возврат рекламодателю | `X-Bot-Secret` |

### Stats (`/stats`)

| Метод | Путь | Описание | Авторизация |
|---|---|---|---|
| `POST` | `/stats/channels/{id}/refresh` | Обновить статистику канала | JWT (owner/manager) |

### Bot Actions (`/bot`)

Все эндпоинты защищены заголовком `X-Bot-Secret`.

| Метод | Путь | Описание |
|---|---|---|
| `POST` | `/bot/users/upsert` | Создать/обновить пользователя |
| `POST` | `/bot/users/{tg_user_id}/wallet` | Привязать кошелёк |
| `POST` | `/bot/channels` | Создать/обновить канал |
| `GET` | `/bot/channels` | Список каналов пользователя (по `tg_user_id`) |
| `POST` | `/bot/listings` | Создать листинг (требуется `linked_wallet`, иначе 400) |
| `POST` | `/bot/requests` | Создать заявку |
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
| `POST` | `/bot/deals/{id}/advertiser_brief` | Бриф рекламодателя с медиа и пожеланием publish_at |
| `POST` | `/bot/deals/{id}/events` | Добавить событие сделки |
| `POST` | `/bot/tamper` | Отметить пост как изменённый |
| `POST` | `/bot/deleted` | Отметить пост как удалённый |

---

## Сервисы

### deal_service.py

- `can_transition(current, new_status)` — проверка допустимости перехода
- `set_status(deal, new_status)` — установка нового статуса (с логированием)
- `log_event(db, deal_id, type, payload)` — запись DealEvent

### escrow_service.py

- `create_deposit(db, deal, expected_amount)` — генерация нового кошелька, шифрование ключа, создание EscrowPayment, переход в `AWAITING_PAYMENT`
- `confirm_payment(db, deal, payment, tx_hash)` — подтверждение оплаты, переход в `FUNDED`
- `scan_incoming_payments(db)` — сканирование всех ожидающих депозитов, автоподтверждение при обнаружении транзакции
- `release_payment(db, deal, payout_address)` — отправка средств владельцу канала, переход в `RELEASED`
- `refund_payment(db, deal, refund_address, reason)` — возврат средств рекламодателю, переход в `REFUNDED`

### ton_escrow.py

Интеграция с блокчейном TON через toncenter API (v2 + v3):

- `create_deposit_wallet(deal_id)` — генерация нового TON-кошелька (v4r2)
- `encrypt_deposit_key(key)` / `decrypt_deposit_key(value)` — AES-GCM шифрование мнемоники
- `build_deposit_comment(deal_id)` — формирование комментария `deal:<id>`
- `find_incoming_tx(address, amount, comment)` — поиск входящей транзакции по адресу/сумме/комментарию
- `send_payout(key, address, amount)` — отправка TON на адрес выплаты
- `send_refund(key, address, amount)` — отправка TON на адрес возврата
- Поддержка кошельков: v1r1–v4r2, v5r1 (автоопределение версии)
- Fallback: v3 API → v2 API при ошибках
- Retry: до 3 попыток при transient-ошибках

### stats_service.py

- `fetch_stats(chat_id)` — получение статистики канала через MTProto (Telethon, `GetBroadcastStatsRequest`)
- `fetch_bot_api_subscribers(chat_id)` — fallback: количество подписчиков через Bot API

### telegram_service.py

- `send_message(chat_id, text, reply_markup)` — отправка текстового сообщения
- `send_media(chat_id, text, media_items)` — отправка медиа (photo/video/document/animation, группа или одиночное)
- `copy_message(from_chat_id, message_id, to_chat_id)` — копирование сообщения (для проверки удалённых постов)

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

---

## Worker

### `worker/__main__.py`

RQ worker (`SimpleWorker` с `TimerDeathPenalty` для Windows). Подключается к Redis, обрабатывает задачи из очереди.

### `worker/scheduler.py`

Бесконечный цикл, ставит 5 задач в очередь каждые 20 секунд:

```
check_payment_timeouts → scan_escrow_deposits → process_scheduled_posts →
check_deleted_posts → check_verification_windows → sleep(20) → повтор
```

> Tamper detection выполняется отдельным watcher-ботом (см. `docs/watcher.md`).

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
| Telegram | requests (Bot API), Telethon (MTProto) |
| Валидация | Pydantic v2 + pydantic-settings |
