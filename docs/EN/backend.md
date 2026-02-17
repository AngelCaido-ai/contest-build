# Backend Module

REST API on **FastAPI** with PostgreSQL (SQLAlchemy ORM), TON blockchain escrow integration, Telegram notifications, and background tasks via Redis + RQ.

## Table of Contents

- [Structure](#structure)
- [Configuration](#configuration-coreconfigpy)
- [Authentication and Security](#authentication-and-security)
- [Data Models](#data-models)
- [Deal Statuses (DealStatus)](#deal-statuses-dealstatus)
- [API Endpoints](#api-endpoints)
- [Services](#services)
- [Background Tasks](#background-tasks-tasksdeal_taskspy)
- [Worker](#worker)
- [Escrow Flow](#escrow-flow-full-cycle)
- [Migrations (Alembic)](#migrations-alembic)
- [Running](#running)
- [Tech Stack](#tech-stack)

## Structure

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
│       ├── 0006_sweep_fields.py
│       ├── 0007_extended_channel_stats.py
│       └── 0008_datetime_timezone_aware.py
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI entry point
│   ├── queue.py                   # Redis queue (RQ)
│   ├── api/
│   │   ├── deps.py                # Dependencies: get_db, get_current_user, get_bot_secret
│   │   └── routes/
│   │       ├── auth.py            # Auth (miniapp, bot)
│   │       ├── bot_actions.py     # Bot actions (upsert, deals, creative, tamper, ...)
│   │       ├── health.py          # Health check (DB + Redis)
│   │       ├── channels.py       # CRUD channels and managers
│   │       ├── deals.py           # CRUD deals (miniapp)
│   │       ├── escrow.py          # Escrow: deposit
│   │       ├── listings.py       # CRUD listings
│   │       ├── requests.py        # CRUD requests
│   │       └── stats.py           # Channel statistics
│   ├── core/
│   │   ├── config.py             # Settings (pydantic-settings)
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
│   ├── schemas/                   # Pydantic schemas (request/response)
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
│   │   ├── deal_actions.py        # Shared deal business logic (constants, helpers, do_* operations)
│   │   ├── deal_service.py         # Status transitions, event logging
│   │   ├── escrow_service.py       # Deposit creation, confirmation, release, refund
│   │   ├── stats_service.py       # MTProto + Bot API (fallback) statistics
│   │   ├── telegram_service.py    # Message/media sending via Bot API
│   │   └── ton_escrow.py          # TON blockchain: wallets, transactions, encryption
│   └── tasks/
│       └── deal_tasks.py          # Background tasks (timeouts, scanning, posting, verification)
├── worker/
│   ├── __init__.py
│   ├── __main__.py                # RQ worker (SimpleWorker/WindowsWorker)
│   └── scheduler.py               # Task scheduler (20 sec cycle)
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

## Configuration (`core/config.py`)

Class `Settings` (pydantic-settings), reads `.env`:

| Variable | Type | Default | Description |
|---|---|---|---|
| `APP_NAME` | `str` | `contest` | Application name |
| `DATABASE_URL` | `str` | `postgresql+psycopg2://...` | PostgreSQL connection string |
| `REDIS_URL` | `str` | `redis://localhost:6379/0` | Redis connection string |
| `BOT_TOKEN` | `str` | `""` | Telegram bot token |
| `BOT_SECRET` | `str` | **required** | Shared secret for bot auth |
| `JWT_SECRET` | `str` | **required, min 32 chars** | JWT secret |
| `JWT_TTL_MINUTES` | `int` | `1440` | JWT lifetime (24 hours) |
| `TELETHON_API_ID` | `int?` | `None` | API ID for MTProto (Telethon) |
| `TELETHON_API_HASH` | `str?` | `None` | API Hash for MTProto |
| `TELETHON_SESSION` | `str?` | `None` | Telethon session file |
| `TON_HOT_WALLET` | `str?` | `None` | TON hot wallet mnemonic |
| `TON_API_KEY` | `str?` | `None` | toncenter API key |
| `TON_NETWORK` | `str` | `mainnet` | TON network (`mainnet` / `testnet`) |
| `TON_API_URL` | `str` | `https://toncenter.com/api/v2` | toncenter base URL |
| `TON_API_TIMEOUT_SECONDS` | `int` | `10` | toncenter request timeout |
| `TON_WALLET_VERSION` | `str?` | `None` | Wallet version (`v4r2`, `v5r1`, ...) |
| `TON_WALLET_ID` | `int?` | `None` | Wallet ID for V5 |
| `TON_WALLET_SUBWALLET` | `int?` | `None` | Subwallet for V5 |
| `TON_RESERVE_TON` | `float` | `0.02` | TON reserve for fees |
| `TON_DEPOSIT_COMMENT_PREFIX` | `str` | `deal` | Deposit comment prefix |
| `ESCROW_SECRET_KEY` | `str?` | `None` | AES key for deposit_key encryption |
| `BOT_LOG_CHAT_ID` | `int?` | `None` | Chat ID for deleted post check |
| `PAYMENT_TIMEOUT_MINUTES` | `int` | `1440` | Payment wait timeout (24 hours) |
| `VERIFICATION_WINDOW_MINUTES` | `int` | `60` | Post verification window (60 min) |
| `SWEEP_DELAY_MINUTES` | `int` | `5` | Delay before sweep after release/refund |
| `SWEEP_MIN_BALANCE_TON` | `float` | `0.005` | Min balance for sweep (below — fee eats all) |
| `RATE_LIMIT_ESCROW_DEPOSIT` | `str` | `10/minute` | Limit for `POST /escrow/deals/{id}/deposit` (key `user_id` from JWT) |
| `RATE_LIMIT_ESCROW_BOT` | `str` | `20/minute` | Limit for escrow bot-only endpoints and `POST /bot/deals/{id}/deposit` (key IP) |
| `INIT_DATA_MAX_AGE_SECONDS` | `int` | `300` | Max age of `auth_date` in Telegram `init_data` (replay attack protection) |

---

## Authentication and Security

### JWT

- Algorithm: **HS256**
- Payload: `sub` (user_id), `iat`, `exp`
- Lifetime: `JWT_TTL_MINUTES` (default 24 hours)
- Sent in header: `Authorization: Bearer <token>`

### Two Auth Methods

| Endpoint | Method | Caller | Mechanism |
|---|---|---|---|
| `POST /auth/miniapp` | Web App | Mini App (frontend) | Validate `init_data` (HMAC SHA-256 via `bot_token`) |
| `POST /auth/bot` | Bot API | Telegram bot | Header `X-Bot-Secret` |

On first auth user is created automatically with role `advertiser`.

### Bot Endpoint Protection

All routes `/bot/*` are protected by `get_bot_secret` dependency — checks header `X-Bot-Secret`.

### Replay Attack Protection (auth_date)

`verify_init_data` after HMAC check validates `auth_date` from `init_data`:
- If `auth_date` missing or not a number — data rejected.
- If diff between current time and `auth_date` exceeds `INIT_DATA_MAX_AGE_SECONDS` (default 300 sec / 5 min) — data rejected.
- Captured `init_data` string cannot be reused after window expires.

### Timing-Safe Secret Comparison

All secret comparisons use `hmac.compare_digest()` (constant-time) to prevent timing attacks:
- `deps.py` — compare `X-Bot-Secret` with `settings.bot_secret`
- `security.py` — compare computed HMAC with `received_hash` when validating Telegram `init_data`

### Rate Limiting Financial Endpoints

- Via `slowapi` with Redis storage (`REDIS_URL`)
- `POST /escrow/deals/{id}/deposit` — limit `RATE_LIMIT_ESCROW_DEPOSIT`, key: `user_id` from JWT
- `POST /bot/deals/{id}/deposit` — limit `RATE_LIMIT_ESCROW_BOT`, key: IP
- On limit exceeded API returns `429 Too Many Requests`

### TON Address Validation

- `POST /auth/me/wallet` and `POST /bot/users/{tg_user_id}/wallet` — field `linked_wallet` validated as TON address.
- On invalid format API returns `422 Unprocessable Entity`, transaction not sent.

### CORS

`CORSMiddleware` with explicit limits:

| Parameter | Value |
|---|---|
| `allow_origins` | Only from `CORS_ORIGINS` env (comma-separated). Localhost **not** added by default — for dev specify in `.env` |
| `allow_credentials` | `True` |
| `allow_methods` | `GET`, `POST`, `PATCH`, `DELETE`, `OPTIONS` |
| `allow_headers` | `Authorization`, `Content-Type`, `X-Bot-Secret` |

---

## Data Models

### User
| Field | Type | Description |
|---|---|---|
| `id` | `int` PK | User ID |
| `tg_user_id` | `bigint` UNIQUE | Telegram user ID |
| `tg_username` | `str?` UNIQUE | Telegram username (normalized, no @) |
| `roles` | `JSON` | Role list (`["advertiser"]`, `["owner"]`, ...) |
| `linked_wallet` | `str?` | Linked TON wallet |
| `created_at` | `datetime` | Creation date |

### Channel
| Field | Type | Description |
|---|---|---|
| `id` | `int` PK | Channel ID |
| `tg_chat_id` | `bigint` UNIQUE | Telegram chat ID |
| `username` | `str?` | Channel username |
| `title` | `str?` | Channel title |
| `owner_user_id` | `int` FK → users | Owner |
| `bot_admin_status` | `bool` | Bot is channel admin |
| `rights_snapshot` | `JSON?` | Bot rights snapshot |
| `created_at` | `datetime` | Creation date |

### ChannelManager
| Field | Type | Description |
|---|---|---|
| `id` | `int` PK | Record ID |
| `channel_id` | `int` FK → channels | Channel |
| `user_id` | `int` FK → users | Manager |
| `permissions` | `JSON?` | Manager permissions |

### ChannelStats
| Field | Type | Description |
|---|---|---|
| `id` | `int` PK | Record ID |
| `channel_id` | `int` FK → channels UNIQUE | Channel |
| `subscribers` | `int?` | Subscribers |
| `views_per_post` | `int?` | Views per post |
| `shares_per_post` | `int?` | Shares per post |
| `reactions_per_post` | `int?` | Reactions per post |
| `enabled_notifications` | `float?` | Share of subscribers with enabled notifications (0..1) |
| `subscribers_prev` | `int?` | Subscribers (previous period) |
| `views_per_post_prev` | `int?` | Views per post (previous period) |
| `shares_per_post_prev` | `int?` | Shares per post (previous period) |
| `reactions_per_post_prev` | `int?` | Reactions per post (previous period) |
| `languages_json` | `JSON?` | Language distribution `{"English": 0.65, "Russian": 0.35}` |
| `premium_json` | `JSON?` | Premium subscriber share |
| `updated_at` | `datetime` | Last update |
| `source` | `str?` | Data source (`mtproto` / `bot_api`) |

### Listing
| Field | Type | Description |
|---|---|---|
| `id` | `int` PK | Listing ID |
| `channel_id` | `int` FK → channels | Channel |
| `price_ton` | `Numeric(18,8)?` | Price in TON |
| `price_usd` | `Numeric(18,2)?` | Price in USD |
| `format` | `str` | Placement format (default `post`) |
| `categories` | `JSON?` | Categories |
| `constraints` | `JSON?` | Constraints |
| `active` | `bool` | Listing active |
| `created_at` | `datetime` | Creation date |

### Request
| Field | Type | Description |
|---|---|---|
| `id` | `int` PK | Request ID |
| `advertiser_id` | `int` FK → users | Advertiser |
| `budget` | `Numeric(18,2)?` | Budget |
| `niche` | `str?` | Niche |
| `languages` | `JSON?` | Languages |
| `min_subs` | `int?` | Min subscribers |
| `min_views` | `int?` | Min views |
| `dates` | `JSON?` | Placement dates |
| `brief` | `text?` | Brief |
| `created_at` | `datetime` | Creation date |

### Deal
| Field | Type | Description |
|---|---|---|
| `id` | `int` PK | Deal ID |
| `listing_id` | `int?` FK → listings | Source listing |
| `request_id` | `int?` FK → requests | Source request |
| `advertiser_id` | `int` FK → users | Advertiser |
| `channel_id` | `int` FK → channels | Channel |
| `price` | `Numeric(18,2)?` | Deal price |
| `format` | `str?` | Format |
| `brief` | `text?` | Brief |
| `publish_at` | `datetime?` | Publication date |
| `verification_window` | `int?` | Verification window (min) |
| `status` | `DealStatus` | Deal status |
| `posted_message_id` | `bigint?` | Published message ID |
| `posted_at` | `datetime?` | Publication date |
| `verification_started_at` | `datetime?` | Verification start |
| `tampered` | `bool` | Post was edited |
| `deleted` | `bool` | Post was deleted |
| `created_at` | `datetime` | Creation date |
| `updated_at` | `datetime` | Update date |

### EscrowPayment
| Field | Type | Description |
|---|---|---|
| `id` | `int` PK | Record ID |
| `deal_id` | `int` FK → deals UNIQUE | Deal |
| `deposit_address` | `str` | Deposit address |
| `deposit_comment` | `str?` | Transaction comment |
| `deposit_key` | `str?` | Encrypted mnemonic |
| `expected_amount` | `Numeric(18,8)?` | Expected amount |
| `tx_hash` | `str?` | Incoming tx hash |
| `confirmed_at` | `datetime?` | Payment confirmation |
| `release_tx_hash` | `str?` | Release tx hash |
| `refund_tx_hash` | `str?` | Refund tx hash |
| `sweep_tx_hash` | `str?` | Sweep tx hash (or skip marker) |
| `payout_address` | `str?` | Payout address (owner) |
| `refund_address` | `str?` | Refund address (advertiser) |
| `released_at` | `datetime?` | Payout date |
| `refunded_at` | `datetime?` | Refund date |
| `swept_at` | `datetime?` | Sweep date |
| `created_at` | `datetime` | Creation date |

### Creative
| Field | Type | Description |
|---|---|---|
| `id` | `int` PK | Creative ID |
| `deal_id` | `int` FK → deals | Deal |
| `text` | `text?` | Post text |
| `media_file_ids` | `JSON?` | Media files (file_id) |
| `version` | `int` | Version (incremental) |
| `status` | `CreativeStatus` | Status (`DRAFT`, `REVIEW`, `APPROVED`) |
| `created_at` | `datetime` | Creation date |

### DealEvent
| Field | Type | Description |
|---|---|---|
| `id` | `int` PK | Event ID |
| `deal_id` | `int` FK → deals | Deal |
| `type` | `str` | Event type |
| `payload` | `JSON?` | Additional data |
| `created_at` | `datetime` | Creation date |

---

## Deal Statuses (DealStatus)

```
NEGOTIATING → TERMS_LOCKED → AWAITING_PAYMENT → FUNDED →
CREATIVE_DRAFT → CREATIVE_REVIEW → APPROVED →
SCHEDULED → POSTED → VERIFYING → RELEASED
                                            ↘ REFUNDED
Any status (except POSTED/VERIFYING/RELEASED/REFUNDED) → CANCELED
```

### Allowed Transitions

`set_status` enforces this table — on invalid transition throws `InvalidTransitionError`.

| From | To |
|---|---|
| `NEGOTIATING` | `TERMS_LOCKED`, `CANCELED` |
| `TERMS_LOCKED` | `TERMS_LOCKED`, `AWAITING_PAYMENT`, `CANCELED` |
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

### Roles and Allowed Transitions

| Role | Can set statuses |
|---|---|
| `owner` (channel owner / manager) | `TERMS_LOCKED`, `CANCELED`, `SCHEDULED`, `POSTED`, `VERIFYING`, `RELEASED`, `REFUNDED` |
| `advertiser` | `AWAITING_PAYMENT`, `FUNDED`, `CANCELED` |

---

## API Endpoints

### Health (`/health`)

| Method | Path | Description | Auth |
|---|---|---|---|
| `GET` | `/health` | Service health (DB + Redis). 200 — ok, 503 — component unavailable | — |

### Auth (`/auth`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/miniapp` | Auth via Telegram Web App `init_data` |
| `POST` | `/auth/bot` | Auth from bot (`X-Bot-Secret`) |
| `GET` | `/auth/me` | Current user by JWT |
| `POST` | `/auth/me/wallet` | Update current user payout wallet (TON address validated) |

### Channels (`/channels`)

| Method | Path | Description | Auth |
|---|---|---|---|
| `POST` | `/channels/` | Create channel (by `tg_chat_id` or `username`; if only username is given, chat ID is resolved via Telegram `getChat`) | JWT |
| `GET` | `/channels/` | List current user channels (owner + manager) | JWT |
| `GET` | `/channels/{id}` | Get channel | JWT (owner/manager) |
| `PATCH` | `/channels/{id}` | Update channel | JWT (owner) |
| `DELETE` | `/channels/{id}` | Unlink channel (deactivates listings, deletes managers/stats; 409 if active deals exist) | JWT (owner) |
| `POST` | `/channels/{id}/managers` | Add manager | JWT (owner) |
| `GET` | `/channels/{id}/managers` | List managers | JWT (owner) |
| `DELETE` | `/channels/{id}/managers/{mid}` | Remove manager | JWT (owner) |

`GET /channels/` and `GET /channels/{id}` include `stats` (if saved in `channel_stats`).

### Listings (`/listings`)

| Method | Path | Description | Auth |
|---|---|---|---|
| `POST` | `/listings/` | Create listing | JWT (owner) |
| `GET` | `/listings/` | List listings (filters: `price_min`, `price_max`, `active`, `channel_id`, `exclude_own`; pagination: `limit`, `offset`) | JWT |
| `GET` | `/listings/{id}` | Get listing (includes channel preview and stats if present) | JWT |
| `PATCH` | `/listings/{id}` | Update listing | JWT (owner) |

`GET /listings/{id}` also returns `channel` object (id, username, title, stats) for Mini App preview.

### Requests (`/requests`)

| Method | Path | Description | Auth |
|---|---|---|---|
| `POST` | `/requests/` | Create request | JWT |
| `GET` | `/requests/` | List requests (filters: `budget_min`, `budget_max`; pagination: `limit`, `offset`) | JWT |
| `GET` | `/requests/{id}` | Get request | JWT |
| `PATCH` | `/requests/{id}` | Update request | JWT (advertiser) |

### Deals (`/deals`)

| Method | Path | Description | Auth |
|---|---|---|---|
| `POST` | `/deals/` | Create deal (from listing or request); 409 with `deal_id` if active deal exists for listing or for request+channel. For listings the price is taken from `price_usd` (priority) or `price_ton` (fallback); the user cannot override it | JWT |
| `GET` | `/deals/` | List current user deals (pagination: `limit`, `offset`) | JWT |
| `GET` | `/deals/{id}` | Get deal | JWT (participant) |
| `GET` | `/deals/{id}/events` | Deal event history (newest first) | JWT (participant) |
| `POST` | `/deals/{id}/terms` | Lock deal terms | JWT (owner/manager) |
| `POST` | `/deals/{id}/publish_at` | Set publish_at | JWT (owner/manager) |
| `POST` | `/deals/{id}/status` | Change deal status | JWT (by role and transitions) |
| `POST` | `/deals/{id}/creative` | Submit creative | JWT (owner/manager) |
| `GET` | `/deals/{id}/creative` | Get creative (latest or by `version`) | JWT (participant) |
| `POST` | `/deals/{id}/creative/status` | Creative review (APPROVED/DRAFT) | JWT (advertiser) |
| `POST` | `/deals/{id}/advertiser_brief` | Submit advertiser brief (text/media/publish_at) | JWT (advertiser) |
| `POST` | `/deals/media/upload` | Upload file to Telegram and get `file_id` for media_file_ids | JWT |

`GET /deals/{id}` returns extended object (on top of base deal schema) so Mini App can show more context without extra requests.

| Field | Type | Description |
|---|---|---|
| `channel_info` | `object \| null` | Channel summary + stats (if in `channel_stats`) |
| `advertiser_info` | `object \| null` | Advertiser summary |
| `events` | `DealEventOut[]` | Deal event history (sorted by `created_at`) |

### Escrow (`/escrow`)

| Method | Path | Description | Auth |
|---|---|---|---|
| `POST` | `/escrow/deals/{id}/deposit` | Create deposit address | JWT (participant) |

Response `EscrowOut` includes `deal_price` (deal price) and `network_fee` (network fee reserve, = `expected_amount - deal_price`). Field `expected_amount` = `deal_price + TON_RESERVE_TON`.

Endpoints confirm, release, refund removed — worker calls `escrow_service` functions directly, bypassing HTTP.

### Stats (`/stats`)

| Method | Path | Description | Auth |
|---|---|---|---|
| `POST` | `/stats/channels/{id}/refresh` | Refresh channel statistics | JWT (owner/manager) |

### Bot Actions (`/bot`)

All endpoints protected by `X-Bot-Secret` header.

| Method | Path | Description |
|---|---|---|
| `POST` | `/bot/users/upsert` | Create/update user |
| `POST` | `/bot/users/{tg_user_id}/wallet` | Link wallet (TON address validated) |
| `POST` | `/bot/channels` | Create/update channel |
| `GET` | `/bot/channels` | List user channels (by `tg_user_id`) |
| `POST` | `/bot/listings` | Create listing (requires `linked_wallet`, else 400) |
| `GET` | `/bot/listings` | List listings (filters: `price_min`, `price_max`, `active`, `channel_id`; pagination: `limit`, `offset`) |
| `GET` | `/bot/listings/{id}` | Get listing |
| `POST` | `/bot/requests` | Create request |
| `GET` | `/bot/requests` | List requests (filters: `budget_min`, `budget_max`; pagination: `limit`, `offset`) |
| `GET` | `/bot/requests/{id}` | Get request |
| `POST` | `/bot/deals` | Create deal; 409 if active deal exists for listing |
| `GET` | `/bot/deals` | List deals (filters: `tg_user_id`, `statuses`, `role`, `channel_id`, `limit`, `offset`, `order_by`) |
| `GET` | `/bot/deals/{id}` | Get deal |
| `POST` | `/bot/deals/{id}/terms` | Lock deal terms |
| `POST` | `/bot/deals/{id}/publish_at` | Set publication date |
| `POST` | `/bot/deals/{id}/status` | Change deal status |
| `POST` | `/bot/deals/{id}/deposit` | Create deposit |
| `POST` | `/bot/deals/{id}/creative` | Create/submit creative |
| `POST` | `/bot/deals/{id}/creative/status` | Update creative status (approve/reject) |
| `GET` | `/bot/deals/{id}/creative` | Get creative (latest or by version) |
| `POST` | `/bot/deals/{id}/messages` | Send deal message (text/media) |
| `GET` | `/bot/deals/{id}/messages` | Get deal message history |
| `POST` | `/bot/deals/{id}/advertiser_brief` | Advertiser brief with media and publish_at |
| `POST` | `/bot/deals/{id}/events` | Add deal event |
| `POST` | `/bot/tamper` | Mark post as edited |
| `POST` | `/bot/deleted` | Mark post as deleted |

---

## Services

### deal_actions.py

Shared service layer for deal business logic. Extracted from `deals.py` and `bot_actions.py` to remove duplication (~750 lines). Route handlers delegate to `do_*` functions that take `user_id: int` (not `User` or `tg_user_id`), throw `ValueError` on domain errors and `InvalidTransitionError` on invalid status transitions.

**Constants:**
- `ROLE_OWNER`, `ROLE_ADVERTISER` — role string identifiers
- `ROLE_ALLOWED_STATUSES` — statuses each role can set
- `FINAL_DEAL_STATUSES` — terminal statuses (`RELEASED`, `REFUNDED`, `CANCELED`)

**Helpers:**
- `get_deal_role_flags(db, deal, user_id)` → `(is_owner, is_advertiser)` — resolve role by `user_id`; raises `ValueError("channel_not_found")`, `ValueError("not_deal_participant")`
- `get_deal_role(db, deal, user_id)` → `str` — returns `ROLE_OWNER` or `ROLE_ADVERTISER`
- `next_step_for_role(status, role)` → next step hint for notifications
- `format_deal_terms(deal)` → format deal terms
- `deal_action_keyboard(deal, role)` → inline keyboard for Telegram notifications
- `send_deal_notification(deal, user, role, text)` — send notification with hint and keyboard
- `notify_deal_parties(db, deal, text)` — notify both parties
- `send_creative_to_advertiser(deal, creative, advertiser)` — send creative to advertiser

**Business operations:**
- `do_update_terms(db, deal_id, actor_user_id, fields)` → `Deal` — lock terms (strips `price` from fields if deal is linked to a listing with a set price)
- `do_update_publish_at(db, deal_id, actor_user_id, publish_at)` → `Deal` — set publication date
- `do_update_status(db, deal_id, actor_user_id, new_status)` → `Deal` — change status
- `do_create_creative(db, deal_id, actor_user_id, text, media_file_ids)` → `Creative` — create creative
- `do_get_creative(db, deal_id, actor_user_id, version)` → `Creative` — get creative
- `do_update_creative_status(db, deal_id, actor_user_id, new_status, comment, publish_at)` → `Creative` — creative review
- `do_add_advertiser_brief(db, deal_id, actor_user_id, text, media_file_ids, publish_at)` → `DealEvent` — advertiser brief

### deal_service.py

- `InvalidTransitionError(ValueError)` — exception on invalid status transition; contains `deal_id`, `current`, `target`
- `can_transition(current, new_status)` — check transition validity (for UI hints)
- `set_status(deal, new_status)` — set new status with transition enforcement; throws `InvalidTransitionError` if transition not in `ALLOWED_TRANSITIONS`
- `log_event(db, deal_id, type, payload)` — write DealEvent

### escrow_service.py

- `create_deposit(db, deal, expected_amount)` — generate new wallet, encrypt key, create EscrowPayment, transition to `AWAITING_PAYMENT`
- `confirm_payment(db, deal, payment, tx_hash)` — confirm payment, transition to `FUNDED`
- `scan_incoming_payments(db)` — scan all pending deposits, auto-confirm on transaction detection
- `release_payment(db, deal, payout_address)` — send funds to channel owner, transition to `RELEASED`
- `refund_payment(db, deal, refund_address, reason)` — refund to advertiser, transition to `REFUNDED`
- `sweep_deposit(db, deal, payment)` — return remainder (reserve) from deposit wallet to advertiser (mode 128)

**Race condition protection (pessimistic locking):**
All financial ops (`confirm_payment`, `release_payment`, `refund_payment`, `sweep_deposit`) run `SELECT ... FOR UPDATE` on `Deal` and `EscrowPayment` rows before idempotency check. Prevents double TON send on concurrent requests from multiple workers/API. `scan_incoming_payments` locks row only after finding transaction in blockchain, to avoid holding lock during HTTP. `create_deposit_address` in routes/escrow.py similarly locks Deal row before checking existing payment. Background tasks `check_verification_windows` and `sweep_completed_deposits` re-read deal+payment with lock in loop before calling financial functions.

### ton_escrow.py

TON blockchain integration via toncenter API (v2 + v3):

- `create_deposit_wallet(deal_id)` — generate new TON wallet (v4r2); address is generated in **non-bounceable** format to prevent funds from bouncing back on uninitialized contracts
- `_normalize_address(value)` — normalize address to raw format (`wc:hex`) for unambiguous comparison (independent of testnet/bounceable/url-safe flags)
- `encrypt_deposit_key(key)` / `decrypt_deposit_key(value)` — AES-GCM mnemonic encryption; `decrypt_deposit_key` throws `ValueError` on any decrypt error (invalid data, wrong key, corrupted blob)
- `build_deposit_comment(deal_id)` — form comment `deal:<id>`
- `find_incoming_tx(address, amount, comment)` — find incoming tx by address/amount/comment
- `send_payout(key, address, amount)` — send TON to payout address
- `send_refund(key, address, amount)` — send TON to refund address
- `send_sweep(key, address)` — send full remainder to advertiser address (mode 128)
- Wallet support: v1r1–v4r2, v5r1 (auto-detect version)
- Fallback: v3 API → v2 API on errors
- Retry: up to **4 retries** on transient errors (429, 500, 502, 503, 504) and `ConnectionError`
- **Exponential backoff**: 1s → 2s → 4s → 8s between attempts; on `429` respects `Retry-After` header

### stats_service.py

- `fetch_stats(chat_id)` — get channel stats via MTProto (Telethon, `GetBroadcastStatsRequest`)
- `_resolve_async_graph(client, graph)` — resolves `StatsGraphAsync` token via `LoadAsyncGraphRequest` and parses graph data into `{name: fraction}`
- `_parse_graph_json(raw_json)` — parses Telegram stats graph JSON into `{language: fraction}` dict (0..1)
- `fetch_bot_api_subscribers(chat_id)` — fallback: subscriber count via Bot API

### telegram_service.py

All HTTP requests to Telegram Bot API use `requests.Session` with auto retry:
- Up to **3 retries** on transient errors (429, 500, 502, 503, 504)
- **Exponential backoff**: 1s → 2s → 4s between attempts
- On `429 Too Many Requests` respects `Retry-After` header from Telegram
- Timeouts: 30s for normal requests, 60s for file uploads

Functions:

- `send_message(chat_id, text, reply_markup)` — send text message
- `send_media(chat_id, text, media_items)` — send media (photo/video/document/animation, group or single)
- `upload_media_for_user(chat_id, filename, content, content_type)` — upload file to Telegram and get `file_id`
- `copy_message(from_chat_id, message_id, to_chat_id)` — copy message (for deleted post check)
- `get_chat(chat_id_or_username)` — resolve chat by numeric ID or `@username` via `getChat`; returns full chat object
- `get_chat_administrators(chat_id)` — get chat admin list
- `is_chat_admin(chat_id, tg_user_id)` — check if user is admin

---

## Background Tasks (`tasks/deal_tasks.py`)

Run via RQ worker, scheduler enqueues every 20 seconds.

| Task | Description |
|---|---|
| `check_payment_timeouts` | Cancel deals in `AWAITING_PAYMENT` older than `PAYMENT_TIMEOUT_MINUTES` |
| `scan_escrow_deposits` | Scan blockchain for incoming transactions for pending deposits |
| `process_scheduled_posts` | Publish posts to channels for deals with `publish_at ≤ now` and status `APPROVED`/`SCHEDULED` |
| `check_deleted_posts` | Check deleted posts via `copyMessage` to log chat |
| `check_verification_windows` | After window: `release` if post intact, `refund` if edited/deleted |
| `sweep_completed_deposits` | Sweep remainders from deposit wallets after `RELEASED/REFUNDED` with delay `SWEEP_DELAY_MINUTES` |

---

## Worker

### `worker/__main__.py`

RQ worker (`SimpleWorker` with `TimerDeathPenalty` for Windows). Connects to Redis, processes queue tasks.

### `worker/scheduler.py`

Infinite loop, enqueues 6 tasks every 20 seconds with deduplication:

- Each task enqueued with `job_id=task.__name__` — max 1 job per task type in Redis.
- Before `enqueue` checks existing job status via `Job.fetch()`: if `queued`, `started` or `scheduled` — skip enqueue (DEBUG log).
- `result_ttl=0` — completed job results not stored in Redis (tasks return nothing).
- `job_timeout` — stuck task killed by worker, job_id freed for next cycle.

| Task | `job_timeout` (sec) | Reason |
|---|---|---|
| `scan_escrow_deposits` | 120 | HTTP to TonCenter, payment scan |
| `check_verification_windows` | 120 | HTTP to TonCenter, release/refund |
| `sweep_completed_deposits` | 120 | HTTP to TonCenter, sweep transactions |
| `process_scheduled_posts` | 60 | Telegram API |
| `check_deleted_posts` | 60 | Telegram API |
| `check_payment_timeouts` | 30 | DB ops only |

```
scan_escrow_deposits → check_verification_windows → sweep_completed_deposits →
process_scheduled_posts → check_deleted_posts → check_payment_timeouts → sleep(20) → repeat
```

> Tamper/deletion detection is done by the watcher userbot on Telethon (see [watcher.md](watcher.md)).

---

## Escrow Flow (full cycle)

```
1. Owner locks terms              → TERMS_LOCKED
2. Advertiser requests deposit    → TON wallet created, AWAITING_PAYMENT
3. Advertiser sends TON           → scan_escrow_deposits confirms, FUNDED
4. Owner creates creative         → CREATIVE_REVIEW
5. Advertiser approves            → APPROVED
6. Owner sets publish_at          → SCHEDULED
7. process_scheduled_posts        → VERIFYING
8a. Post intact → check_verification_windows → release → RELEASED
8b. Post edited/deleted → refund → REFUNDED
```

---

## Migrations (Alembic)

| Migration | Description |
|---|---|
| `0001_initial` | All tables: users, channels, channel_managers, channel_stats, listings, requests, deals, escrow_payments, creatives, deal_events |
| `0002_escrow_fields` | Added `deposit_key`, `release_tx_hash`, `refund_tx_hash`, `payout_address`, `refund_address`, `released_at`, `refunded_at` |
| `0003_escrow_comment` | Added `deposit_comment` |
| `0004_deal_brief` | Added `brief` to deals |
| `0005_user_tg_username` | Added `tg_username` to users |
| `0006_sweep_fields` | Added `sweep_tx_hash`, `swept_at` for escrow sweep remainders |
| `0007_extended_channel_stats` | Extended channel stats: `shares_per_post`, `reactions_per_post`, `enabled_notifications`, `*_prev` fields for trends |
| `0008_datetime_timezone_aware` | All DateTime columns converted to `TIMESTAMP WITH TIME ZONE` for correct timezone-aware serialization |

---

## Running

```bash
# API server
uvicorn backend.app.main:app --reload

# Worker (task processing)
python -m backend.worker

# Scheduler (enqueue tasks)
python -m backend.worker.scheduler
```

---

## Tech Stack

| Component | Technology |
|---|---|
| Framework | FastAPI |
| ORM | SQLAlchemy 2.0 (mapped_column) |
| DB | PostgreSQL |
| Migrations | Alembic |
| Queue | Redis + RQ |
| JWT | python-jose |
| Blockchain | TON (tonsdk, pytoniq) |
| Encryption | cryptography (AES-GCM) |
| Telegram | requests (Bot API, retry via urllib3), Telethon (MTProto) |
| Validation | Pydantic v2 + pydantic-settings |
