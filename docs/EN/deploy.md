# Server Deployment

## Table of Contents

- [Server](#server)
- [Server Architecture](#server-architecture)
- [Docker Compose Services](#docker-compose-services)
- [Modules and Affected Services](#modules-and-affected-services)
- [Deployment Options](#deployment-options)
- [Rollback](#rollback)
- [Post-Deployment Verification](#post-deployment-verification)
- [Environment Variables](#environment-variables)

## Server

| Parameter | Value |
|---|---|
| IP | `85.239.58.214` |
| User | `root` |
| Project path | `/opt/contest` |
| Docker Compose | all services defined in `docker-compose.yml` |

## Server Architecture

```
/opt/contest/
├── .env                  # secrets (not in repository)
├── docker-compose.yml
├── Dockerfile            # shared image for backend, bot, worker, scheduler, watcher
├── Caddyfile            # reverse proxy → backend:8000
├── requirements.txt
├── backend/              # FastAPI API
├── bot/                  # aiogram bot
├── watcher/              # watcher bot
└── miniapp/              # React Mini App (separate Dockerfile)
```

## Docker Compose Services

| Service | Image | Port | Dependencies |
|---|---|---|---|
| `caddy` | caddy:2 | 80, 443 | backend |
| `postgres` | postgres:15 | 5432 (internal) | — |
| `redis` | redis:7 | 6379 (internal) | — |
| `backend` | contest-backend (build) | 8000 (internal) | postgres, redis |
| `worker` | contest-backend (build) | — | postgres, redis, backend |
| `scheduler` | contest-backend (build) | — | postgres, redis, backend |
| `bot` | contest-backend (build) | — | postgres, redis, backend |
| `watcher` | contest-backend (build) | — | backend |

Services `backend`, `worker`, `scheduler`, `bot`, `watcher` share one Docker image (root Dockerfile).  
On `docker compose up --build <service>`, the shared image is rebuilt and specified services are restarted.

## Modules and Affected Services

| Module | Files in image | Services to restart |
|---|---|---|
| `backend/` | `backend/` | `backend`, `worker`, `scheduler` |
| `bot/` | `bot/` | `bot` |
| `watcher/` | `watcher/` | `watcher` |
| `requirements.txt` | `requirements.txt` | all Python services |
| `docker-compose.yml` | — (outside image) | affected services |
| `Caddyfile` | — (volume mount) | `caddy` |
| `miniapp/` | separate image | `miniapp` (if present) |

## Deployment Options

### Option 1: `deploy.py` script (recommended)

The script uploads changed files via SFTP and rebuilds required containers.

```bash
# Deploy everything (backend + bot + watcher + infra)
python deploy.py --all

# Deploy backend only (backend + worker + scheduler)
python deploy.py --backend

# Deploy bot only
python deploy.py --bot

# Deploy watcher only
python deploy.py --watcher

# Deploy specific files without rebuild
python deploy.py --files backend/app/api/routes/listings.py backend/app/api/deps.py --no-rebuild
```

The script:
1. Connects to server via SSH
2. Creates backups of affected files (`*.bak-<timestamp>`)
3. Uploads files via SFTP
4. Runs `docker compose up -d --build <services>`
5. Checks container status and outputs recent logs

Requirements: `pip install paramiko` (already in system).

### Option 2: Manual deployment via SSH

```bash
# 1. Connect to server
ssh root@85.239.58.214

# 2. Go to project
cd /opt/contest

# 3. Update files (scp from local machine)
# From Windows (PowerShell):
scp backend/app/api/routes/listings.py root@85.239.58.214:/opt/contest/backend/app/api/routes/listings.py

# 4. Rebuild and restart
docker compose up -d --build backend worker scheduler

# 5. Verify
docker compose ps
docker compose logs --tail=30 backend
```

### Option 3: Git on server

If git is configured on server:

```bash
ssh root@85.239.58.214
cd /opt/contest
git pull origin main
docker compose up -d --build
```

## Rollback

The script creates backups before each deployment:

```bash
# On server — find backups
find /opt/contest -name "*.bak-*" -mtime -1

# Restore file
cp /opt/contest/backend/app/api/deps.py.bak-20260211 /opt/contest/backend/app/api/deps.py

# Rebuild
docker compose up -d --build backend worker scheduler
```

## Post-Deployment Verification

```bash
# Container status
docker compose ps

# Backend logs (last 50 lines)
docker compose logs --tail=50 backend

# API check
curl -s https://85-239-58-214.nip.io/listings/ | head -c 200

# Healthcheck
docker compose ps --format "table {{.Name}}\t{{.Status}}"
```

## Environment Variables

File `.env` on server (`/opt/contest/.env`) — not in repository.  
Template: `.env.example` in repository.  
When adding new variables — update `.env` on server manually.
