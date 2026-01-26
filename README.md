# Telegram Ads Marketplace MVP

## Overview
Monorepo for a Telegram Mini App + Bot marketplace with escrow flow, auto posting, and verification.

## Structure
- `backend/` FastAPI API, database, tasks
- `bot/` aiogram bot
- `miniapp/` React Telegram WebApp (Vite)
- `infra/` reserved

## Requirements
- Python 3.11+
- Node.js 18+
- PostgreSQL
- Redis

## Setup
1. Copy `env.example` to `.env` and fill values.
2. Install dependencies: `pip install -r requirements.txt`
3. Start databases: `docker-compose up -d`
4. Run migrations:
   - `cd backend`
   - `alembic upgrade head`

## Run
- API: `uvicorn backend.app.main:app --reload`
- Bot: `python -m bot.app.main`
- Worker: `python -m backend.worker`
- Scheduler: `python backend/worker/scheduler.py`
- Mini App:
  - `cd miniapp`
  - `npm install`
  - `npm run dev`

## Deployment

### Frontend (GitHub Pages)

1. Включите GitHub Pages в настройках репозитория:
   - Settings → Pages → Source: GitHub Actions

2. Настройте Secrets (Settings → Secrets and variables → Actions):
   - `VITE_API_BASE` - URL API бэкенда (например, `https://api.example.com`)
   - `VITE_BOT_URL` - URL Telegram бота (например, `https://t.me/your_bot`)
   - `VITE_BASE_PATH` - базовый путь для GitHub Pages (например, `/contest/` или `/`)

3. Workflow автоматически запустится при push в `main` ветку с изменениями в `miniapp/`

4. После успешного деплоя приложение будет доступно по адресу:
   `https://<username>.github.io/<repository-name>/`

## Notes
- MTProto stats require `TELETHON_API_ID`, `TELETHON_API_HASH`, and `TELETHON_SESSION`.
- If MTProto is not configured, stats fall back to Bot API subscriber count.
- Escrow deposit addresses are placeholders and should be replaced by a real TON integration.
- Mini App env: `VITE_API_BASE`, `VITE_BOT_URL`, `VITE_BASE_PATH`.
