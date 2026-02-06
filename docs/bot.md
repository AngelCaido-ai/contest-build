# Модуль bot

Telegram-бот на **aiogram 3** с FSM (конечный автомат), inline-клавиатурами и синхронным HTTP-клиентом к backend API.

## Структура

```
bot/
├── __init__.py
├── app/
│   ├── __init__.py
│   ├── config.py              # Конфигурация (BotSettings)
│   ├── main.py                # Точка входа, polling
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start.py           # /start — регистрация пользователя
│   │   ├── onboarding.py      # /add_channel — привязка канала
│   │   ├── marketplace.py     # Маркетплейс: листинги, заявки, меню, сделки (список), менеджеры, кошелёк
│   │   └── deals.py           # Управление отдельной сделкой: условия, статус, креатив, эскроу
│   └── services/
│       ├── __init__.py
│       └── api_client.py      # Синхронный HTTP-клиент к backend API
```

---

## Конфигурация (`config.py`)

Класс `BotSettings` (pydantic-settings), читает переменные окружения:

| Переменная     | Тип   | По умолчанию              | Описание                        |
|----------------|-------|---------------------------|---------------------------------|
| `BOT_TOKEN`    | str   | —                         | Токен Telegram-бота             |
| `API_BASE_URL` | str   | `http://localhost:8000`   | Базовый URL backend API         |
| `BOT_SECRET`   | str   | —                         | Секрет для заголовка X-Bot-Secret |

Валидатор `normalize_env` снимает лишние кавычки и пробелы из значений переменных.

---

## Точка входа (`main.py`)

Функция `main()`:
1. Создаёт экземпляр `Bot` и проверяет подключение (`get_me`).
2. Создаёт `Dispatcher` с `MemoryStorage` для FSM.
3. Подключает роутеры в порядке: `start` → `onboarding` → `marketplace` → `deals`.
4. Удаляет вебхук и запускает polling.

> Tamper detection (отслеживание правок постов) выполняется отдельным watcher-ботом — см. `docs/watcher.md`.

---

## Обработчики (handlers)

### `start.py` — Команда `/start`

Регистрирует/обновляет пользователя через `api_client.upsert_user` и выводит список доступных команд.

### `onboarding.py` — Команда `/add_channel`

Привязка Telegram-канала к платформе:
1. Принимает `@username` или числовой `chat_id`.
2. Проверяет, что пользователь — администратор канала.
3. Проверяет статус бота в канале (`bot_admin`).
4. Отправляет данные в backend через `api_client.create_channel`.

### `marketplace.py` — Маркетплейс

Основной хендлер для навигации и CRUD-операций. Содержит:

#### Команды

| Команда              | Описание                                               |
|----------------------|--------------------------------------------------------|
| `/menu`              | Главное inline-меню                                    |
| `/wallet`            | Установка TON-кошелька для выплат                      |
| `/cancel`            | Отмена текущего FSM-потока                             |
| `/listings`          | Список листингов                                       |
| `/requests`          | Список заявок рекламодателей                           |
| `/channels`          | Список своих каналов                                   |
| `/assigned_channels` | Каналы, где пользователь — менеджер (не владелец)      |
| `/create_listing`    | Создание листинга (FSM или одной командой)             |
| `/create_request`    | Создание заявки (FSM или одной командой)               |
| `/respond_request`   | Откликнуться на заявку и создать сделку                |
| `/deals`             | Список сделок с фильтрами и пагинацией                 |
| `/add_manager`       | Добавить менеджера канала                              |
| `/list_managers`     | Список менеджеров канала                               |
| `/remove_manager`    | Удалить менеджера канала                               |

#### FSM-состояния (States)

| StatesGroup          | Состояния                          | Назначение                                 |
|----------------------|------------------------------------|--------------------------------------------|
| `ListingCreateState` | `channel_id`, `price_usd`, `format`| Пошаговое создание листинга                |
| `ListingRespondState`| `listing_id`, `price_usd`, `format`, `brief` | Отклик на листинг (создание сделки) |
| `RequestCreateState` | `budget`, `brief`                  | Пошаговое создание заявки                  |
| `WalletState`        | `address`                          | Установка TON-кошелька                     |
| `ManagerAddState`    | `channel_id`, `username`           | Добавление менеджера                       |
| `ManagerListState`   | `channel_id`                       | Выбор канала для списка менеджеров         |
| `ManagerRemoveState` | `channel_id`, `username`, `confirm`| Удаление менеджера с подтверждением        |
| `DealListFilterState`| `channel_id`                       | Фильтр сделок по каналу                   |

#### Callback-меню

Inline-кнопки с префиксами:
- `menu:main`, `menu:listings`, `menu:requests`, `menu:deals`, `menu:create_listing`, `menu:create_request`, `menu:wallet` — навигация по разделам.
- `listing:`, `listing_respond:`, `request:` — детали и отклики.
- `listing_channel:`, `listing_channel_manual` — выбор канала для листинга.
- `manager_channel:`, `manager_channel_manual`, `manager_remove_confirm:` — управление менеджерами.
- `deals_page:`, `deals_status:`, `deals_role:`, `deals_channel:`, `deals_clear`, `deals_active_clear` — фильтры и пагинация сделок.
- `flow_back:`, `flow_cancel:` — навигация «Назад» / «Отмена» в FSM-потоках.

#### Фильтры сделок

Группы статусов:

| Ключ          | Метка        | Статусы                                       |
|---------------|--------------|-----------------------------------------------|
| `all`         | Все          | все                                           |
| `negotiating` | Переговоры   | NEGOTIATING, TERMS_LOCKED                     |
| `payment`     | Оплата       | AWAITING_PAYMENT, FUNDED                      |
| `creative`    | Креатив      | CREATIVE_DRAFT, CREATIVE_REVIEW               |
| `publish`     | Публикация   | APPROVED, SCHEDULED, POSTED                   |
| `verify`      | Проверка     | VERIFYING                                     |
| `done`        | Завершенные  | RELEASED, REFUNDED, CANCELED                  |

Роли фильтра: `all`, `owner` (мои каналы), `advertiser` (я рекламодатель).

#### Вспомогательные функции

- `_extract_channel_ref` — парсит ссылки `t.me/...`, `@username`, числовые id, приватные ссылки `t.me/c/...`.
- `_resolve_channel_id` — полная резолюция канала: поиск в базе, запрос Telegram API, автопривязка.
- `_find_channel` — поиск канала в локальном списке по `id`, `tg_chat_id`, `username`.
- `_link_channel` — привязка канала (проверка прав, создание через API).

---

### `deals.py` — Управление сделкой

Полный workflow одной сделки: условия, статусы, креативы, эскроу-платежи.

#### Команды

| Команда             | Описание                                            |
|---------------------|-----------------------------------------------------|
| `/deal DEAL_ID`     | Открыть детали сделки (становится активной)         |
| `/terms DEAL_ID ...`| Установить условия сделки одной командой            |
| `/status DEAL_ID STATUS` | Сменить статус сделки                          |
| `/creative DEAL_ID [TEXT]`| Отправить креатив                             |
| `/creative_status DEAL_ID STATUS [COMMENT\|PUBLISH_AT]` | Обновить статус креатива |

#### Жизненный цикл сделки (статусы)

```
NEGOTIATING → TERMS_LOCKED → AWAITING_PAYMENT → FUNDED
    → CREATIVE_DRAFT → CREATIVE_REVIEW → APPROVED
    → SCHEDULED → POSTED → VERIFYING → RELEASED / REFUNDED
                                      ↘ CANCELED (из большинства статусов)
```

#### Допустимые переходы по ролям

**Owner (владелец канала):**
- TERMS_LOCKED, CANCELED, SCHEDULED, POSTED, VERIFYING, RELEASED, REFUNDED

**Advertiser (рекламодатель):**
- AWAITING_PAYMENT, FUNDED, CANCELED

#### FSM-состояния

| StatesGroup          | Состояния                                    | Назначение                        |
|----------------------|----------------------------------------------|-----------------------------------|
| `DealTermsState`     | `price`, `publish_at`, `verification_window`, `format` | Обновление условий сделки |
| `DealStatusState`    | `status`                                     | Смена статуса сделки              |
| `DealPublishAtState` | `publish_at`                                 | Установка времени публикации      |
| `CreativeState`      | `content`                                    | Отправка креатива (текст/медиа)   |
| `CreativeStatusState`| `status`, `comment`, `publish_at`            | Ревью креатива рекламодателем     |
| `DealSwitchState`    | `confirm`                                    | Переключение между сделками       |

#### Callback-префиксы

- `deal:` — детали сделки
- `deal_terms:`, `deal_terms_back:`, `deal_terms_cancel:` — редактирование условий
- `deal_status:`, `deal_status_set:`, `deal_status_back:`, `deal_status_cancel:` — смена статуса
- `deal_payment:` — детали эскроу-оплаты (TON)
- `deal_creative:`, `deal_creative_back:`, `deal_creative_cancel:` — создание креатива
- `deal_creative_status:`, `deal_creative_status_set:`, `deal_creative_status_back:`, `deal_creative_status_cancel:` — ревью креатива
- `deal_creative_view:`, `deal_creative_previous:` — просмотр креативов (текущий и предыдущие версии)
- `deal_publish_at:`, `deal_publish_at_back:`, `deal_publish_at_cancel:` — установка времени публикации
- `deal_switch:` — переключение между сделками с сохранением/сбросом черновика
- `deal_draft_resume:`, `deal_draft_clear:` — возобновление/удаление черновика

#### Механизм черновиков

При переключении между сделками незавершённый FSM-поток сохраняется как черновик в `state.data[DEAL_DRAFTS_KEY]`. Пользователь может:
- **Сохранить черновик и перейти** к другой сделке.
- **Сбросить и перейти** — черновик удаляется.
- **Отмена** — остаться в текущем потоке.

Черновик можно возобновить кнопкой «Продолжить черновик» в карточке сделки.

#### Pinned-сообщение активной сделки

Активная сделка закрепляется (pin) в чате. При обновлении данных сделки закреплённое сообщение обновляется через `edit_message_text`. Если редактирование невозможно — создаётся новое и закрепляется.

#### Подсказки по следующему шагу (`_next_step_for_role`)

Для каждого статуса и роли выводится текстовая подсказка, что делать дальше:
- Owner в NEGOTIATING → «Lock terms or cancel the deal.»
- Advertiser в TERMS_LOCKED → «Pay escrow (Payment details).»
- Owner в FUNDED → «Create and submit creative.»
- и т.д.

#### Эскроу-платёж (Payment details)

Для рекламодателя формируется ссылка на оплату в TON:
- `ton://transfer/...` — стандартная deep-link
- `https://app.tonkeeper.com/transfer/...` — Tonkeeper

Сумма передаётся в наноTON. Если сумма превышает цену сделки — показывается примечание о резерве на комиссии.

#### Креативы

- Owner создаёт креатив (текст и/или медиа: фото, видео, анимация, документ).
- Advertiser ревьюит: DRAFT (с комментарием для доработки) или APPROVED.
- При одобрении без `publish_at` запрашивается время публикации.
- Поддержка медиагрупп (до нескольких файлов).
- Просмотр предыдущих версий креатива.

---

## API-клиент (`api_client.py`)

Синхронный HTTP-клиент на `requests`. Все запросы к backend идут с заголовком `X-Bot-Secret`. Для операций с менеджерами используется JWT-авторизация через `auth_bot`.

### Методы

| Метод                    | HTTP           | Путь                                  | Описание                         |
|--------------------------|----------------|---------------------------------------|----------------------------------|
| `upsert_user`            | POST           | `/bot/users/upsert`                  | Создать/обновить пользователя    |
| `auth_bot`               | POST           | `/auth/bot`                           | Получить JWT-токен для пользователя |
| `create_channel`         | POST           | `/bot/channels`                       | Привязать канал                  |
| `list_channels`          | GET            | `/bot/channels`                       | Список каналов пользователя     |
| `list_channel_managers`  | GET            | `/channels/{id}/managers`             | Список менеджеров канала         |
| `add_channel_manager`    | POST           | `/channels/{id}/managers`             | Добавить менеджера               |
| `remove_channel_manager` | DELETE         | `/channels/{id}/managers/{mid}`       | Удалить менеджера                |
| `list_listings`          | GET            | `/listings`                           | Список листингов                 |
| `get_listing`            | GET            | `/listings/{id}`                      | Детали листинга                  |
| `create_listing`         | POST           | `/bot/listings`                       | Создать листинг                  |
| `list_requests`          | GET            | `/requests`                           | Список заявок                    |
| `get_request`            | GET            | `/requests/{id}`                      | Детали заявки                    |
| `create_request`         | POST           | `/bot/requests`                       | Создать заявку                   |
| `list_deals`             | GET            | `/bot/deals`                          | Список сделок (с фильтрами)     |
| `get_deal`               | GET            | `/bot/deals/{id}`                     | Детали сделки                    |
| `create_deal`            | POST           | `/bot/deals`                          | Создать сделку                   |
| `update_terms`           | POST           | `/bot/deals/{id}/terms`               | Обновить условия сделки          |
| `update_publish_at`      | POST           | `/bot/deals/{id}/publish_at`          | Обновить время публикации        |
| `update_status`          | POST           | `/bot/deals/{id}/status`              | Сменить статус сделки            |
| `create_creative`        | POST           | `/bot/deals/{id}/creative`            | Создать/обновить креатив         |
| `get_creative`           | GET            | `/bot/deals/{id}/creative`            | Получить креатив (с версией)     |
| `update_creative_status` | POST           | `/bot/deals/{id}/creative/status`     | Обновить статус креатива         |
| `create_deposit`         | POST           | `/bot/deals/{id}/deposit`             | Создать эскроу-депозит           |
| `add_event`              | POST           | `/bot/deals/{id}/events`              | Добавить событие сделки          |
| `update_wallet`          | POST           | `/bot/users/{tg_user_id}/wallet`      | Обновить TON-кошелёк             |
| `mark_tamper`            | POST           | `/bot/tamper`                         | Отметить редактирование поста    |
| `mark_deleted`           | POST           | `/bot/deleted`                        | Отметить удаление поста          |

---

## Зависимости

- **aiogram 3** — Telegram Bot Framework (Router, FSM, InlineKeyboard)
- **pydantic / pydantic-settings** — конфигурация
- **requests** — HTTP-клиент к backend

## Запуск

```bash
python -m bot.app.main
```

Требуемые переменные окружения: `BOT_TOKEN`, `BOT_SECRET`, `API_BASE_URL`.
