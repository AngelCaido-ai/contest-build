# Bot Module

Telegram bot on **aiogram 3** with FSM (finite state machine), inline keyboards, and async HTTP client to backend API.

## Table of Contents

- [Structure](#structure)
- [Configuration](#configuration-configpy)
- [Entry Point](#entry-point-mainpy)
- [Handlers](#handlers-handlers)
- [Inline Calendar](#inline-calendar-keyboardscalendarpy)
- [API Client](#api-client-api_clientpy)
- [Dependencies](#dependencies)
- [Running](#running)

## Structure

```
bot/
├── __init__.py
├── app/
│   ├── __init__.py
│   ├── config.py              # Configuration (BotSettings)
│   ├── main.py                # Entry point, polling
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start.py           # /start — user registration
│   │   ├── onboarding.py      # /add_channel — channel binding
│   │   ├── marketplace.py     # Marketplace: listings, requests, menu, deals (list), managers, wallet
│   │   └── deals.py           # Single deal management: terms, status, creative, escrow
│   ├── keyboards/
│   │   ├── __init__.py
│   │   └── calendar.py        # Inline calendar for publish date/time selection
│   └── services/
│       ├── __init__.py
│       └── api_client.py       # Async HTTP client to backend API (httpx)
```

---

## Configuration (`config.py`)

Class `BotSettings` (pydantic-settings), reads environment variables:

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `BOT_TOKEN` | str | — | Telegram bot token |
| `API_BASE_URL` | str | `http://localhost:8000` | Backend API base URL |
| `BOT_SECRET` | str | — | Secret for X-Bot-Secret header |
| `REDIS_URL` | str | `redis://localhost:6379/1` | Redis URL for FSM storage (DB 1, separate from RQ on DB 0) |
| `MINIAPP_URL` | str | `""` (empty) | Mini App URL (when set, payment button opens Mini App payment page via WebAppInfo) |

Validator `normalize_env` strips extra quotes and whitespace from variable values.

---

## Entry Point (`main.py`)

Function `main()`:
1. Creates `Bot` instance and checks connection (`get_me`).
2. Creates `Dispatcher` with `RedisStorage` for FSM (persistent storage, data survives restarts).
3. Registers routers in order: `calendar` → `start` → `onboarding` → `marketplace` → `deals`.
4. Removes webhook.
5. Initializes singleton `httpx.AsyncClient` via `api_client.init_client()`.
6. Starts polling; on stop closes client via `api_client.close_client()`.

> Tamper detection (post edit monitoring) is done by separate watcher bot — see [watcher.md](watcher.md).

---

## Handlers

### `start.py` — Command `/start`

Registers/updates user via `api_client.upsert_user` and shows available commands.

Supports deep link parameter `deal_{id}` (format: `/start deal_123`). When present, activates specified deal in chat — same as `/deal DEAL_ID`. Used by "Go to bot" button in Mini App.

### `onboarding.py` — Command `/add_channel`

Bind Telegram channel to platform:
1. Accepts `@username` or numeric `chat_id`.
2. Verifies user is channel admin.
3. Verifies bot status in channel (`bot_admin`).
4. Sends data to backend via `api_client.create_channel`.

### `marketplace.py` — Marketplace

Main handler for navigation and CRUD. Contains:

#### Commands

| Command | Description |
|---------|-------------|
| `/menu` | Main inline menu |
| `/wallet` | Set TON wallet for payouts |
| `/cancel` | Cancel current FSM flow |
| `/listings` | List listings (paginated, 8 per page) |
| `/requests` | List advertiser requests (paginated, 8 per page) |
| `/channels` | List own channels |
| `/assigned_channels` | Channels where user is manager (not owner) |
| `/create_listing` | Create listing (FSM or single command) |
| `/create_request` | Create request (FSM or single command) |
| `/respond_request` | Respond to request and create deal |
| `/deals` | List deals with filters and pagination |
| `/add_manager` | Add channel manager |
| `/list_managers` | List channel managers |
| `/remove_manager` | Remove channel manager |

#### FSM States

| StatesGroup | States | Purpose |
|-------------|--------|---------|
| `ListingCreateState` | `channel_id`, `price_usd`, `format` | Stepwise listing creation |
| `ListingRespondState` | `listing_id`, `price_usd`, `format`, `brief`, `publish_at`, `creative` | Respond to listing (create deal) |
| `RequestCreateState` | `budget`, `brief` | Stepwise request creation |
| `WalletState` | `address` | Set TON wallet |
| `ManagerAddState` | `channel_id`, `username` | Add manager |
| `ManagerListState` | `channel_id` | Select channel for manager list |
| `ManagerRemoveState` | `channel_id`, `username`, `confirm` | Remove manager with confirmation |
| `DealListFilterState` | `channel_id` | Deal filter by channel |

#### Callback Menu

Inline buttons with prefixes:
- `menu:main`, `menu:listings`, `menu:requests`, `menu:deals`, `menu:create_listing`, `menu:create_request`, `menu:wallet` — section navigation.
- `listing:`, `listing_respond:`, `request:` — details and responses.
- `listing_channel:`, `listing_channel_manual` — channel selection for listing.
- `manager_channel:`, `manager_channel_manual`, `manager_remove_confirm:` — manager management.
- `deals_page:`, `deals_status:`, `deals_role:`, `deals_channel:`, `deals_clear`, `deals_active_clear` — deal filters and pagination.
- `flow_back:`, `flow_cancel:` — Back / Cancel in FSM flows.

#### Deal Filters

Status groups:

| Key | Label | Statuses |
|-----|-------|----------|
| `all` | All | all |
| `negotiating` | Negotiations | NEGOTIATING, TERMS_LOCKED |
| `payment` | Payment | AWAITING_PAYMENT, FUNDED |
| `creative` | Creative | CREATIVE_DRAFT, CREATIVE_REVIEW |
| `publish` | Publishing | APPROVED, SCHEDULED, POSTED |
| `verify` | Verification | VERIFYING |
| `done` | Completed | RELEASED, REFUNDED, CANCELED |

Role filters: `all`, `owner` (my channels), `advertiser` (I am advertiser).

#### Helper Functions

- `_extract_channel_ref` — parses links `t.me/...`, `@username`, numeric ids, private links `t.me/c/...`.
- `_resolve_channel_id` — full channel resolution: DB lookup, Telegram API request, auto-link.
- `_find_channel` — find channel in local list by `id`, `tg_chat_id`, `username`.
- `_link_channel` — link channel (rights check, create via API).

---

### `deals.py` — Deal Management

Full single-deal workflow: terms, statuses, creatives, escrow payments.

#### Commands

| Command | Description |
|---------|-------------|
| `/deal DEAL_ID` | Open deal details (becomes active) |
| `/terms DEAL_ID ...` | Set deal terms in one command |
| `/creative DEAL_ID [TEXT]` | Submit creative |
| `/creative_status DEAL_ID STATUS [COMMENT\|PUBLISH_AT]` | Update creative status |

#### Deal Lifecycle (Statuses)

```
NEGOTIATING → TERMS_LOCKED → AWAITING_PAYMENT → FUNDED
    → CREATIVE_DRAFT → CREATIVE_REVIEW → APPROVED
    → SCHEDULED → POSTED → VERIFYING → RELEASED / REFUNDED
                                      ↘ CANCELED (from most statuses)
```

#### FSM States

| StatesGroup | States | Purpose |
|-------------|--------|---------|
| `DealTermsState` | `price`, `publish_at`, `verification_window`, `format` | Update deal terms |
| `DealPublishAtState` | `publish_at` | Set publication time |
| `CreativeState` | `content` | Submit creative (text/media) |
| `CreativeStatusState` | `status`, `comment`, `publish_at` | Advertiser creative review |
| `DealMessageState` | `content` | Send deal message |
| `DealSwitchState` | `confirm` | Switch between deals |

#### Callback Prefixes

- `deal:` — deal details
- `deal_terms:`, `deal_terms_back:`, `deal_terms_cancel:` — edit terms
- `deal_payment:` — escrow payment details (TON)
- `deal_creative:`, `deal_creative_back:`, `deal_creative_cancel:` — create creative
- `deal_creative_status:`, `deal_creative_status_set:`, `deal_creative_status_back:`, `deal_creative_status_cancel:` — creative review
- `deal_creative_view:`, `deal_creative_previous:` — view creatives (current and previous versions)
- `deal_publish_at:`, `deal_publish_at_back:`, `deal_publish_at_cancel:` — set publication time
- `deal_msg:`, `deal_msg_back:`, `deal_msg_cancel:`, `deal_msg_history:` — deal messaging
- `deal_switch:` — switch between deals with draft save/discard
- `deal_draft_resume:`, `deal_draft_clear:` — resume/clear draft

#### Draft Mechanism

When switching between deals, unfinished FSM flow is saved as draft in `state.data[DEAL_DRAFTS_KEY]`. User can:
- **Save draft and switch** to another deal.
- **Discard and switch** — draft removed.
- **Cancel** — stay in current flow.

Draft can be resumed via "Resume draft" button in deal card.

#### Pinned Message for Active Deal

Active deal is pinned in chat. On deal data update, pinned message is updated via `edit_message_text`. If edit not possible — new message is created and pinned.

#### Next Step Hints (`_next_step_for_role`)

For each status and role a text hint shows what to do next:
- Owner in NEGOTIATING → "Lock terms or cancel the deal."
- Advertiser in TERMS_LOCKED → "Pay escrow (Payment details)."
- Owner in FUNDED → "Create and submit creative."
- etc.

#### Escrow Payment (Payment details)

When `MINIAPP_URL` is set, "Pay in app" button opens Mini App payment page (`/deals/{id}/pay`) via Telegram `WebAppInfo`. The page uses TonConnect to send the transaction directly from Mini App.

When `MINIAPP_URL` is not set (fallback), external wallet links are shown:
- `ton://transfer/...` — standard deep-link
- `https://app.tonkeeper.com/transfer/...` — Tonkeeper

Amount in nanoTON. If amount exceeds deal price — note about reserve for fees is shown.

#### Creatives

- Owner creates creative (text and/or media: photo, video, animation, document).
- Advertiser reviews: DRAFT (with comment for revision) or APPROVED.
- On approve without `publish_at` — publication time is requested.
- Media groups supported (multiple files).
- View previous creative versions.

#### Deal Messaging

- Both sides can send message from deal card via "Send message" button.
- Text and media supported (photo, video, animation, document).
- Message stored as `DealEvent(type="MESSAGE")`.
- Counterparty receives notification with quick buttons: Open deal / Reply / History.
- "Message history" button shows recent messages and "More" pagination.

---

## Inline Calendar (`keyboards/calendar.py`)

Widget for convenient publish date/time selection via inline keyboard. Replaces manual ISO string input.

### Flow

1. **Calendar** — current month day grid with ◀/▶ navigation. Past days inactive. Today highlighted `[N]`.
2. **Hours** — buttons 00–23 (4 rows of 6). "◀ Back" returns to calendar.
3. **Minutes** — buttons with 5-min step (:00, :05, …, :55). "◀ Back" returns to hours.
4. **Result** — ISO string `YYYY-MM-DDTHH:MM:00+03:00` (MSK).

### Callback Prefixes

| Prefix | Purpose |
|--------|---------|
| `dtp:nav:` | Month navigation |
| `dtp:day:` | Day selection |
| `dtp:hr:` | Hour selection |
| `dtp:mn:` | Minute selection (final) |
| `dtp:ign` | Inactive button (placeholder) |
| `dtp:skip` | Skip (for optional fields) |

### Usage Contexts

| Context | FSM State | Required | Next Step |
|---------|-----------|----------|-----------|
| `terms` | `DealTermsState.publish_at` | Yes | → `verification_window` |
| `publish_at` | `DealPublishAtState.publish_at` | Yes | → update publish_at, deal card |
| `creative_status` | `CreativeStatusState.publish_at` | Yes | → approve creative, deal card |
| `listing_respond` | `ListingRespondState.publish_at` | No (skip) | → `creative` |

### Text Fallback

If user types text instead of using calendar, these formats accepted:
- `15.02 18:30` — date without year (current year, MSK)
- `15.02.2026 18:30` — date with year (MSK)
- ISO 8601 (`2026-02-15T18:30:00+03:00`)

---

## API Client (`api_client.py`)

Async HTTP client on `httpx.AsyncClient`. Singleton created at bot start (`init_client()`) and reused for connection pooling. Timeout: 10s full request, 5s connect. All backend requests use `X-Bot-Secret` header. For manager operations JWT auth via `auth_bot` is used. On bot stop client is closed (`close_client()`).

### Lifecycle

| Function | Description |
|----------|-------------|
| `init_client()` | Creates `httpx.AsyncClient` with `base_url`, `timeout`, `headers` |
| `close_client()` | Closes client (`await client.aclose()`) |
| `_get_client()` | Returns client, throws `RuntimeError` if not initialized |

### Methods

| Method | HTTP | Path | Description |
|--------|------|------|-------------|
| `upsert_user` | POST | `/bot/users/upsert` | Create/update user |
| `auth_bot` | POST | `/auth/bot` | Get JWT for user |
| `create_channel` | POST | `/bot/channels` | Link channel |
| `list_channels` | GET | `/bot/channels` | List user channels |
| `list_channel_managers` | GET | `/channels/{id}/managers` | List channel managers |
| `add_channel_manager` | POST | `/channels/{id}/managers` | Add manager |
| `remove_channel_manager` | DELETE | `/channels/{id}/managers/{mid}` | Remove manager |
| `list_listings` | GET | `/listings` | List listings (`limit`, `offset`) |
| `get_listing` | GET | `/listings/{id}` | Listing details |
| `create_listing` | POST | `/bot/listings` | Create listing |
| `list_requests` | GET | `/requests` | List requests (`limit`, `offset`) |
| `get_request` | GET | `/requests/{id}` | Request details |
| `create_request` | POST | `/bot/requests` | Create request |
| `list_deals` | GET | `/bot/deals` | List deals (with filters) |
| `get_deal` | GET | `/bot/deals/{id}` | Deal details |
| `create_deal` | POST | `/bot/deals` | Create deal |
| `create_advertiser_brief` | POST | `/bot/deals/{id}/advertiser_brief` | Advertiser brief with media |
| `create_deal_message` | POST | `/bot/deals/{id}/messages` | Send deal message |
| `list_deal_messages` | GET | `/bot/deals/{id}/messages` | Deal message history |
| `update_terms` | POST | `/bot/deals/{id}/terms` | Update deal terms |
| `update_publish_at` | POST | `/bot/deals/{id}/publish_at` | Update publication time |
| `update_status` | POST | `/bot/deals/{id}/status` | Change deal status |
| `create_creative` | POST | `/bot/deals/{id}/creative` | Create/update creative |
| `get_creative` | GET | `/bot/deals/{id}/creative` | Get creative (with version) |
| `update_creative_status` | POST | `/bot/deals/{id}/creative/status` | Update creative status |
| `create_deposit` | POST | `/bot/deals/{id}/deposit` | Create escrow deposit |
| `add_event` | POST | `/bot/deals/{id}/events` | Add deal event |
| `update_wallet` | POST | `/bot/users/{tg_user_id}/wallet` | Update TON wallet |
| `mark_tamper` | POST | `/bot/tamper` | Mark post as edited |
| `mark_deleted` | POST | `/bot/deleted` | Mark post as deleted |

---

## Dependencies

- **aiogram 3** — Telegram Bot Framework (Router, FSM, InlineKeyboard)
- **pydantic / pydantic-settings** — configuration
- **httpx** — async HTTP client to backend (connection pooling, timeout)
- **redis** — async client for RedisStorage (FSM persistence)

## Running

```bash
python -m bot.app.main
```

Required env vars: `BOT_TOKEN`, `BOT_SECRET`, `API_BASE_URL`, `REDIS_URL`.
Optional: `MINIAPP_URL` (for Mini App payment button).
