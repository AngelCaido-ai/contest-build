# Внедрение Sentry

## Текущее состояние мониторинга

Проект не имеет внешнего мониторинга ошибок. Все логи уходят в stdout/stderr Docker-контейнеров.

| Компонент | Логирование | Обработка ошибок |
|---|---|---|
| backend (FastAPI) | `logging.basicConfig(level=INFO)` + `logger.exception()` | Global exception handler → 500 + лог |
| worker (RQ) | Через модули backend | try/except в каждой задаче |
| scheduler | Нет | Нет try/except в цикле `while True` |
| bot (aiogram) | `logging.basicConfig(level=INFO)` | try/except в `main()` |
| watcher (aiogram) | `logging.basicConfig(level=INFO)` | try/except в `main()` |
| miniapp (React) | Нет | Нет ErrorBoundary, ошибки JS невидимы |

Алертинга нет. Health check эндпоинтов нет. Об ошибках узнаём по жалобам пользователей или при ручной проверке `docker compose logs`.

## Зачем нужен Sentry

### 1. Финансовые операции без контроля

Шесть фоновых задач крутятся каждые 20 секунд через scheduler → RQ:

- `scan_escrow_deposits` — сканирование блокчейна на входящие платежи
- `sweep_completed_deposits` — сбор остатков с deposit-кошельков
- `check_payment_timeouts` — отмена просроченных оплат
- `process_scheduled_posts` — автопубликация в каналы
- `check_deleted_posts` — детекция удалённых постов
- `check_verification_windows` — release/refund по окну верификации

Если `scan_escrow_deposits` начнёт падать — пользователь отправит TON, а система не увидит платёж. Деньги «зависнут» без уведомления.

### 2. Scheduler без защиты

```python
# backend/worker/scheduler.py
def main() -> None:
    while True:
        queue.enqueue(check_payment_timeouts)
        queue.enqueue(scan_escrow_deposits)
        # ...
        time.sleep(20)
```

Цикл не обёрнут в try/except. Одно исключение (например, потеря связи с Redis) — и все 6 задач перестанут планироваться. Контейнер при этом не упадёт (`while True` просто прервётся), Docker не перезапустит его, и всё будет выглядеть «работающим».

### 3. Много точек отказа

8 Docker-сервисов: caddy, postgres, redis, backend, worker, scheduler, bot, watcher. Каждый может упасть независимо. Docker `restart: unless-stopped` перезапускает контейнер, но не сообщает о причине падения.

### 4. Внешние API могут сломаться без предупреждения

- **Telegram Bot API** — rate limits, изменения API
- **Telethon (MTProto)** — сессия может протухнуть, FloodWait
- **TON RPC (toncenter)** — нестабильные ноды, таймауты, изменения формата ответа

Без мониторинга тренд «Telethon начал возвращать ошибки 3 часа назад» невидим.

### 5. Ручной деплой без CI/CD

Деплой через `deploy.py` (SSH/SFTP). Нет автоматических тестов в пайплайне. Если после обновления backend начнёт падать на конкретном эндпоинте — без Sentry это обнаружится случайно.

### 6. Mini App без мониторинга

React-приложение работает в браузере пользователя. Ошибки JS (TypeError, network failure, несовместимость браузера) полностью невидимы серверу.

## Что покрывает Sentry

| Проблема | Решение Sentry |
|---|---|
| Ошибка в фоновой задаче | Алерт с полным стектрейсом и контекстом (deal_id, payment_id) |
| Scheduler перестал работать | Sentry Crons — алерт, если задача не выполнилась по расписанию |
| Внешний API начал сбоить | Группировка ошибок + тренды — видно рост ошибок по конкретной интеграции |
| Регрессия после деплоя | Release tracking — привязка новых ошибок к конкретному релизу |
| Ошибка JS в Mini App | `@sentry/react` — стектрейс + устройство + браузер пользователя |
| Медленные запросы | Performance tracing — latency по эндпоинтам и задачам |
| Повторяющаяся ошибка | Дедупликация + счётчик — не 1000 писем, а одно с «happened 1000 times» |

## План интеграции

### Backend (FastAPI)

Пакет: `sentry-sdk[fastapi]`

Интеграция автоматическая — SDK перехватывает ошибки в роутах, middleware и фоновых задачах.

Точка входа: `backend/app/main.py` — инициализация до создания `FastAPI()`.

Что даёт:
- Автоматический перехват unhandled exceptions
- Контекст запроса (URL, метод, headers, user)
- Performance tracing по эндпоинтам

### Worker (RQ)

Пакет: `sentry-sdk[rq]`

Интеграция автоматическая — SDK подключается к RQ worker и перехватывает ошибки в задачах.

Точка входа: `backend/worker/__main__.py` — инициализация до создания Worker.

Что даёт:
- Стектрейс с контекстом задачи (имя функции, аргументы)
- Привязка к конкретной сделке через `sentry_sdk.set_tag("deal_id", ...)`

### Scheduler

Пакет: `sentry-sdk` + Sentry Crons

Точка входа: `backend/worker/scheduler.py` — инициализация в `main()`, обёртка цикла.

Что даёт:
- Алерт, если цикл упал (Crons monitor)
- Перехват ошибок при `queue.enqueue()`
- Видимость, что scheduler жив и работает

### Bot и Watcher (aiogram)

Пакет: `sentry-sdk`

Точка входа: `bot/app/main.py` и `watcher/app/main.py` — инициализация до создания Bot/Dispatcher.

Aiogram не имеет встроенной интеграции с Sentry, поэтому:
- Middleware aiogram для автоматического `capture_exception()` при ошибке в handler
- Или ручной вызов `sentry_sdk.capture_exception()` в существующих try/except блоках

### Mini App (React)

Пакет: `@sentry/react`

Точка входа: `miniapp/src/main.tsx` — инициализация до `ReactDOM.createRoot()`.

Что даёт:
- Автоматический перехват ошибок JS
- ErrorBoundary с fallback UI
- Breadcrumbs (клики, навигация, XHR)
- Session replay (опционально)

## Конфигурация

Новые переменные окружения:

| Переменная | Где используется | Пример |
|---|---|---|
| `SENTRY_DSN` | backend, worker, scheduler | `https://xxx@o123.ingest.sentry.io/456` |
| `SENTRY_BOT_DSN` | bot | Отдельный DSN для разделения ошибок бота |
| `SENTRY_WATCHER_DSN` | watcher | Отдельный DSN или тот же, с тегом `service=watcher` |
| `VITE_SENTRY_DSN` | miniapp | DSN для фронтенда (публичный, без секретов) |
| `SENTRY_ENVIRONMENT` | все сервисы | `production` / `staging` / `development` |
| `SENTRY_RELEASE` | все сервисы | Версия или git commit hash |

Альтернатива: один DSN на все Python-сервисы + тег `service` для фильтрации.

В `docker-compose.yml` пробросить через `environment` или `.env`.

## Стоимость

**Sentry Developer plan (бесплатный):**
- 1 пользователь
- 5 000 ошибок/месяц
- 10 000 транзакций performance/месяц
- Crons monitoring

Для MVP этого достаточно. При росте нагрузки — Team plan ($26/мес) или self-hosted альтернатива (GlitchTip).

## Оценка трудозатрат

| Шаг | Оценка |
|---|---|
| Регистрация проекта в Sentry, получение DSN | 10 мин |
| Интеграция backend + worker | 30 мин |
| Интеграция scheduler + Crons | 30 мин |
| Интеграция bot + watcher | 30 мин |
| Интеграция miniapp | 30 мин |
| Добавление env-переменных в docker-compose и .env | 10 мин |
| Проверка на staging | 30 мин |
| **Итого** | **~3 часа** |
