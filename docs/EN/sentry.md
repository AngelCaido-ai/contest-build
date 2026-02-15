# Sentry Integration

## Current Monitoring State

The project has no external error monitoring. All logs go to Docker container stdout/stderr.

| Component | Logging | Error Handling |
|---|---|---|
| backend (FastAPI) | `logging.basicConfig(level=INFO)` + `logger.exception()` | Global exception handler → 500 + log |
| worker (RQ) | Via backend modules | try/except in each task |
| scheduler | None | No try/except in `while True` loop |
| bot (aiogram) | `logging.basicConfig(level=INFO)` | try/except in `main()` |
| watcher (aiogram) | `logging.basicConfig(level=INFO)` | try/except in `main()` |
| miniapp (React) | None | No ErrorBoundary, JS errors invisible |

No alerting. No health check endpoints. Errors are discovered via user reports or manual `docker compose logs` checks.

## Why Sentry

### 1. Unmonitored Financial Operations

Six background tasks run every 20 seconds via scheduler → RQ:

- `scan_escrow_deposits` — blockchain scan for incoming payments
- `sweep_completed_deposits` — collecting residuals from deposit wallets
- `check_payment_timeouts` — canceling overdue payments
- `process_scheduled_posts` — auto-posting to channels
- `check_deleted_posts` — deleted post detection
- `check_verification_windows` — release/refund by verification window

If `scan_escrow_deposits` starts failing — user sends TON but system does not see payment. Funds get stuck without notification.

### 2. Unprotected Scheduler

```python
# backend/worker/scheduler.py
def main() -> None:
    while True:
        queue.enqueue(check_payment_timeouts)
        queue.enqueue(scan_escrow_deposits)
        # ...
        time.sleep(20)
```

The loop is not wrapped in try/except. One exception (e.g. Redis connection loss) — and all 6 tasks stop being scheduled. The container may not crash (`while True` just breaks), Docker will not restart it, everything looks "working".

### 3. Many Failure Points

8 Docker services: caddy, postgres, redis, backend, worker, scheduler, bot, watcher. Each can fail independently. Docker `restart: unless-stopped` restarts the container but does not report the cause.

### 4. External APIs Can Fail Without Warning

- **Telegram Bot API** — rate limits, API changes
- **Telethon (MTProto)** — session can expire, FloodWait
- **TON RPC (toncenter)** — unstable nodes, timeouts, response format changes

Without monitoring, the trend "Telethon started returning errors 3 hours ago" is invisible.

### 5. Manual Deploy Without CI/CD

Deploy via `deploy.py` (SSH/SFTP). No automated tests in pipeline. If backend starts failing on a specific endpoint after update — without Sentry it is discovered by chance.

### 6. Mini App Without Monitoring

React app runs in user's browser. JS errors (TypeError, network failure, browser incompatibility) are completely invisible to the server.

## What Sentry Covers

| Problem | Sentry Solution |
|---|---|
| Error in background task | Alert with full stacktrace and context (deal_id, payment_id) |
| Scheduler stopped working | Sentry Crons — alert if task did not run on schedule |
| External API started failing | Error grouping + trends — visible rise of errors per integration |
| Regression after deploy | Release tracking — link new errors to specific release |
| JS error in Mini App | `@sentry/react` — stacktrace + device + user browser |
| Slow requests | Performance tracing — latency per endpoints and tasks |
| Recurring error | Deduplication + counter — not 1000 emails, but one with "happened 1000 times" |

## Integration Plan

### Backend (FastAPI)

Package: `sentry-sdk[fastapi]`

Automatic integration — SDK captures errors in routes, middleware, and background tasks.

Entry point: `backend/app/main.py` — initialize before creating `FastAPI()`.

Provides:
- Automatic capture of unhandled exceptions
- Request context (URL, method, headers, user)
- Performance tracing per endpoints

### Worker (RQ)

Package: `sentry-sdk[rq]`

Automatic integration — SDK hooks into RQ worker and captures task errors.

Entry point: `backend/worker/__main__.py` — initialize before creating Worker.

Provides:
- Stacktrace with task context (function name, arguments)
- Link to deal via `sentry_sdk.set_tag("deal_id", ...)`

### Scheduler

Package: `sentry-sdk` + Sentry Crons

Entry point: `backend/worker/scheduler.py` — initialize in `main()`, wrap loop.

Provides:
- Alert if loop crashed (Crons monitor)
- Error capture on `queue.enqueue()`
- Visibility that scheduler is alive and running

### Bot and Watcher (aiogram)

Package: `sentry-sdk`

Entry point: `bot/app/main.py` and `watcher/app/main.py` — initialize before creating Bot/Dispatcher.

Aiogram has no built-in Sentry integration, so:
- Aiogram middleware for automatic `capture_exception()` on handler error
- Or manual `sentry_sdk.capture_exception()` in existing try/except blocks

### Mini App (React)

Package: `@sentry/react`

Entry point: `miniapp/src/main.tsx` — initialize before `ReactDOM.createRoot()`.

Provides:
- Automatic capture of JS errors
- ErrorBoundary with fallback UI
- Breadcrumbs (clicks, navigation, XHR)
- Session replay (optional)

## Configuration

New environment variables:

| Variable | Where used | Example |
|---|---|---|
| `SENTRY_DSN` | backend, worker, scheduler | `https://xxx@o123.ingest.sentry.io/456` |
| `SENTRY_BOT_DSN` | bot | Separate DSN for bot error isolation |
| `SENTRY_WATCHER_DSN` | watcher | Separate DSN or same with tag `service=watcher` |
| `VITE_SENTRY_DSN` | miniapp | DSN for frontend (public, no secrets) |
| `SENTRY_ENVIRONMENT` | all services | `production` / `staging` / `development` |
| `SENTRY_RELEASE` | all services | Version or git commit hash |

Alternative: one DSN for all Python services + `service` tag for filtering.

Pass via `environment` or `.env` in `docker-compose.yml`.

## Cost

**Sentry Developer plan (free):**
- 1 user
- 5,000 errors/month
- 10,000 performance transactions/month
- Crons monitoring

Sufficient for MVP. For higher load — Team plan ($26/mo) or self-hosted alternative (GlitchTip).

## Effort Estimate

| Step | Estimate |
|---|---|
| Register project in Sentry, obtain DSN | 10 min |
| Backend + worker integration | 30 min |
| Scheduler + Crons integration | 30 min |
| Bot + watcher integration | 30 min |
| Miniapp integration | 30 min |
| Add env vars to docker-compose and .env | 10 min |
| Verify on staging | 30 min |
| **Total** | **~3 hours** |
