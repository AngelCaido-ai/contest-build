# Деплой на сервер

## Table of Contents

- [Сервер](#сервер)
- [Архитектура на сервере](#архитектура-на-сервере)
- [Сервисы Docker Compose](#сервисы-docker-compose)
- [Модули и какие сервисы затрагиваются](#модули-и-какие-сервисы-затрагиваются)
- [Варианты деплоя](#варианты-деплоя)
- [Откат](#откат)
- [Проверка после деплоя](#проверка-после-деплоя)
- [Переменные окружения](#переменные-окружения)

## Сервер

| Параметр | Значение |
|---|---|
| IP | `85.239.58.214` |
| Пользователь | `root` |
| Путь проекта | `/opt/contest` |
| Docker Compose | все сервисы описаны в `docker-compose.yml` |

## Архитектура на сервере

```
/opt/contest/
├── .env                  # секреты (не в репозитории)
├── docker-compose.yml
├── Dockerfile            # общий образ для backend, bot, worker, scheduler, watcher
├── Caddyfile             # reverse proxy → backend:8000
├── requirements.txt
├── backend/              # FastAPI API
├── bot/                  # aiogram бот
├── watcher/              # watcher бот
└── miniapp/              # React Mini App (отдельный Dockerfile)
```

## Сервисы Docker Compose

| Сервис | Образ | Порт | Зависимости |
|---|---|---|---|
| `caddy` | caddy:2 | 80, 443 | backend |
| `postgres` | postgres:15 | 5432 (internal) | — |
| `redis` | redis:7 | 6379 (internal) | — |
| `backend` | contest-backend (build) | 8000 (internal) | postgres, redis |
| `worker` | contest-backend (build) | — | postgres, redis, backend |
| `scheduler` | contest-backend (build) | — | postgres, redis, backend |
| `bot` | contest-backend (build) | — | postgres, redis, backend |
| `watcher` | contest-backend (build) | — | backend |

Сервисы `backend`, `worker`, `scheduler`, `bot`, `watcher` используют один Docker-образ (Dockerfile в корне).  
При `docker compose up --build <service>` пересобирается общий образ и перезапускаются указанные сервисы.

## Модули и какие сервисы затрагиваются

| Модуль | Файлы в образе | Сервисы для перезапуска |
|---|---|---|
| `backend/` | `backend/` | `backend`, `worker`, `scheduler` |
| `bot/` | `bot/` | `bot` |
| `watcher/` | `watcher/` | `watcher` |
| `requirements.txt` | `requirements.txt` | все Python-сервисы |
| `docker-compose.yml` | — (вне образа) | затронутые сервисы |
| `Caddyfile` | — (volume mount) | `caddy` |
| `miniapp/` | отдельный образ | `miniapp` (если есть) |

## Варианты деплоя

### Вариант 1: Скрипт `deploy.py` (рекомендуется)

Скрипт загружает изменённые файлы по SFTP и пересобирает нужные контейнеры.

```bash
# Задеплоить всё (backend + bot + watcher + infra)
python deploy.py --all

# Задеплоить только backend (backend + worker + scheduler)
python deploy.py --backend

# Задеплоить только бота
python deploy.py --bot

# Задеплоить только watcher
python deploy.py --watcher

# Задеплоить конкретные файлы без пересборки
python deploy.py --files backend/app/api/routes/listings.py backend/app/api/deps.py --no-rebuild
```

Скрипт:
1. Подключается по SSH к серверу
2. Создаёт бэкапы затрагиваемых файлов (`*.bak-<timestamp>`)
3. Загружает файлы по SFTP
4. Выполняет `docker compose up -d --build <services>`
5. Проверяет статус контейнеров и выводит последние логи

Требования: `pip install paramiko` (уже в системе).

### Вариант 2: Ручной деплой по SSH

```bash
# 1. Подключиться к серверу
ssh root@85.239.58.214

# 2. Перейти в проект
cd /opt/contest

# 3. Обновить файлы (scp с локальной машины)
# Из Windows (PowerShell):
scp backend/app/api/routes/listings.py root@85.239.58.214:/opt/contest/backend/app/api/routes/listings.py

# 4. Пересобрать и перезапустить
docker compose up -d --build backend worker scheduler

# 5. Проверить
docker compose ps
docker compose logs --tail=30 backend
```

### Вариант 3: Git на сервере

Если на сервере настроен git:

```bash
ssh root@85.239.58.214
cd /opt/contest
git pull origin main
docker compose up -d --build
```

## Откат

Скрипт создаёт бэкапы перед каждым деплоем:

```bash
# На сервере — найти бэкапы
find /opt/contest -name "*.bak-*" -mtime -1

# Восстановить файл
cp /opt/contest/backend/app/api/deps.py.bak-20260211 /opt/contest/backend/app/api/deps.py

# Пересобрать
docker compose up -d --build backend worker scheduler
```

## Проверка после деплоя

```bash
# Статус контейнеров
docker compose ps

# Логи backend (последние 50 строк)
docker compose logs --tail=50 backend

# Проверка API
curl -s https://85-239-58-214.nip.io/listings/ | head -c 200

# Проверка healthcheck
docker compose ps --format "table {{.Name}}\t{{.Status}}"
```

## Переменные окружения

Файл `.env` на сервере (`/opt/contest/.env`) — не в репозитории.  
Шаблон: `.env.example` в репозитории.  
При добавлении новых переменных — обновить `.env` на сервере вручную.
