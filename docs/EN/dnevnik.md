# Dnevnik (Change Log)

## 2026-01-27

### backend
- Added bot endpoints for listing/request creation and deal listing by tg user id.
- Added Docker image for API and workers with migrations on startup.
- Fixed alembic migration path (run from backend directory).

### bot
- Added marketplace commands to list/create listings and requests, plus list deals.
- Extended bot API client to cover new marketplace endpoints.
- Added BOT_TOKEN guard in docker-compose to keep container running when token is empty.
- Normalized bot env vars by trimming whitespace and quotes.
- Removed .env file reading from pydantic_settings, using only Docker environment variables.
- Fixed bot startup command (bash instead of sh, added env vars debugging).
- Added logging on bot startup to debug Telegram API connection.

### miniapp
- Added Dockerfile to run the Vite dev server in Docker.

### infra
- Expanded docker-compose with all services, healthchecks, and dependencies.
- Enabled loading env vars from both `.env` and `env` in docker-compose.
- Fixed YAML syntax for bot command (multiline format).
- Bot now reads only `.env` file (empty values in `env` were overwriting `.env` values).
- Backend/worker/scheduler now read only `.env` to avoid BOT_SECRET overwrite.
- BOT_SECRET is now explicitly passed to backend and bot via environment.

### docs
- Added this change log file.
- Documented one-command Docker startup in README.

## 2026-02-04

### backend
- Added bot auth endpoint for JWT without Mini App and API refund flow test.
- Fixed refund API test import path for running from repo root.
- Strengthened refund API test assertions and send_refund call checks.
- Added testnet-gated refund API integration test.
- Added logging and explicit skip reasons in testnet refund test.
- Added explicit source mnemonics support and address mismatch warning in testnet refund test.
- Added non-bounceable deposit address handling and source balance/seqno logs for testnet refund test.
- Added release API tests (mock and testnet) with logging.

## 2026-02-09

### miniapp
- In DealDetailPage block "Deal Master" renamed to "Step-by-step scenario".
- Complete Mini App restructure: monolithic App.tsx split into 6 pages with routing (react-router-dom HashRouter).
- Switched to `@telegram-tools/ui-kit` UI library (ThemeProvider, Button, Input, Group, GroupItem, Text, Select, Toast, SkeletonElement, Spinner).
- Removed custom shadcn components (button.tsx, card.tsx, input.tsx) — replaced with ui-kit.
- Added pages: ListingsPage, RequestsPage, ChannelsPage, DealsPage, DealDetailPage, PaymentPage.
- Added AuthContext — centralized auth via Telegram initData + JWT.
- Added API client (api/client.ts) with typed apiFetch<T>.
- Added universal hook useApi<T> (data, loading, error, refetch).
- Added useBackButton hook for Telegram BackButton integration.
- Added DealStatusBadge — colored badge by deal status (13 statuses).
- Added EmptyState — empty state component.
- Added Layout with bottom tab navigation (4 tabs: Catalog, Requests, Channels, Deals).
- Integrated TonConnect (@tonconnect/ui-react): wallet connection, transaction sending.
- Added PaymentPage: deposit address QR code, TonConnect Pay button.
- Data types moved to types/index.ts (Listing, RequestItem, Deal, Channel, Manager, DealEvent, EscrowPayment, User, DealStatus).
- Extended env.d.ts: themeParams, BackButton, colorScheme.
- New dependencies: react-router-dom, @telegram-tools/ui-kit, @tonconnect/ui-react, qrcode.react.
- Added pages AddChannelPage, CreateListingPage, CreateRequestPage and WalletPage; connected new routes and CTA buttons.
- DealDetailPage extended with action blocks: terms, status, publish_at, creative, creative review, advertiser brief, creative view.
- ListingDetailPage and RequestDetailPage extended with response fields (price/format/publish_at/verification_window/brief) before deal creation.
- In key flow miniapp added file upload to Telegram via backend endpoint `/deals/media/upload` (returns `file_id`), instead of manual JSON `media_file_ids`.
- Added `DateTimePickerField` (datetime-local + quick presets) and replaced manual ISO date input in response and deal management forms.
- In DealDetailPage added deal master mode with step progress and Back/Next navigation.

### backend
- Added JWT workflow endpoints: `/deals/{id}/terms`, `/publish_at`, `/status`, `/creative`, `/creative/status`, `/creative` (GET), `/advertiser_brief`.
- Added Mini App profile endpoints: `GET /auth/me`, `POST /auth/me/wallet`.
- Added JWT endpoint `/deals/media/upload` for file upload to Telegram and `file_id` for `media_file_ids`.
- Added bot deal messaging endpoints: `POST /bot/deals/{id}/messages`, `GET /bot/deals/{id}/messages` with message storage in `DealEvent(type="MESSAGE")`.

### bot
- In `deals.py` added "Send message" and "Message history" buttons, FSM `DealMessageState.content`, text/media sending and history view with pagination.
- In notification to counterpart added quick actions Open deal / Reply / History.

### docs
- Updated `docs/backend.md` with new JWT deal management and wallet endpoints.
- Updated `docs/backend.md` with endpoint `/deals/media/upload`.
- Updated `docs/backend.md` and `docs/bot.md` with deal messaging flow.

## 2026-02-16

### backend
- Fixed missing Telegram notification on deal creation (response to request/listing). Both `bot_create_deal` (`/bot/deals`) and `create_deal` (`/deals`) now call `notify_deal_parties` after successful deal creation, sending deal terms to both advertiser and channel owner.
- Added duplicate deal prevention for requests: `POST /deals` now returns 409 if an active deal already exists for the same `request_id` + `channel_id`.
- 409 responses for both listings and requests now include `deal_id` of the existing active deal in the response body.

### miniapp
- Added `ApiError` class to API client (`client.ts`) — preserves HTTP status code and structured `detail` from backend.
- `RequestDetailPage` and `ListingDetailPage`: on 409 conflict, the app now navigates to the existing deal instead of showing an error toast.

### docs
- Added Sentry integration plan (`docs/RU/sentry.md`) and linked it from the Future Work section in README.md.

### miniapp
- Replaced raw JSON textarea for listing constraints with structured UI: Select for language (single choice) and text Input for geo/countries (comma-separated, multiple).
- `ListingDetailPage`: constraints now displayed as separate GroupItems (Language, Geo) instead of raw JSON.
- Removed manual status change UI (Status Change dropdown and "Update Status" button) from `DealDetailPage`. Users can no longer manually set deal statuses.

### bot
- Removed "Change status" inline button from deal card and all related callback handlers (`deal_status_start`, `deal_status_set`, `deal_status_back`, `deal_status_cancel`, `deal_status_value`).
- Removed `/status` command that allowed manual deal status changes without permission checks.
- Cleaned up `DealStatusState` FSM state, status transition constants (`ALLOWED_TRANSITIONS`, `ROLE_ALLOWED_STATUSES`, `STATUS_ORDER`, `DEAL_STATUSES`), and helper functions (`_status_keyboard`, `_status_label`, `_sorted_statuses`, `_allowed_transitions_for_role`).

### docs
- Updated `bot.md` (RU/EN): removed `/status` command, `DealStatusState`, status callback prefixes, and role-based transition section.

### miniapp
- Added waiting-status hint banner in `DealDetailPage`: when the other party must act next, a contextual message is shown (e.g. "Waiting for the channel owner to set deal terms" for the advertiser in NEGOTIATING status). Covers both advertiser and owner waiting states across the full deal lifecycle.
- Improved form input visibility: added global CSS styles for all text inputs, textareas, and selects — secondary background (`--tg-theme-secondary-bg-color`) and border (`--tg-theme-hint-color`) so inputs no longer blend with block backgrounds. Focus state highlights border with link color. Removed redundant inline Tailwind styles from `DealDetailPage`, `ListingDetailPage`, `RequestDetailPage`, `CreateRequestPage`, and `DateTimePickerField`.
- Added pagination to all list endpoints and UIs:
  - Backend: `GET /deals`, `GET /listings`, `GET /requests` (miniapp) and `GET /bot/listings`, `GET /bot/requests` (bot) now accept `limit` (1-50, default 20) and `offset` (default 0) query parameters with `order_by` sorting.
  - Bot: `list_listings` and `list_requests` API client methods now accept `limit`/`offset`. Bot handlers `_send_listings` and `_send_requests` use paginated fetching (8 per page) with Prev/Next inline keyboard buttons. Added `listings_page:` and `requests_page:` callback handlers.
  - Miniapp: Added `usePaginatedApi` hook (fetches PAGE_SIZE+1 to detect hasMore) and `Pagination` component. `DealsPage`, `ListingsPage`, and `RequestsPage` now paginate (20 per page) with Previous/Next buttons.

### backend
- Added `get_chat(chat_id_or_username)` function to `telegram_service.py` — resolves chat by numeric ID or `@username` via Telegram `getChat` API.
- `ChannelCreate` schema: `tg_chat_id` is now optional; a `model_validator` requires either `tg_chat_id` or `username`.
- `POST /channels/` endpoint: when only `username` is provided, resolves `tg_chat_id` via `telegram_service.get_chat()` and auto-fills `title` from Telegram response.

### miniapp
- `AddChannelPage`: added mode switcher (By Username / By Chat ID). Default mode is "By Username" — user enters `@username` and the backend resolves the channel automatically. "By Chat ID" mode preserved for advanced users.

### backend
- Added `DELETE /channels/{id}` endpoint — owner can unlink a channel. Deactivates related listings, deletes managers and stats. Returns 409 if there are active (non-terminal) deals referencing the channel.

### miniapp
- `ChannelsPage`: added channel detail section showing Channel ID and Username when a channel is selected. Owner sees "Unlink Channel" button with a confirmation dialog. On success the channel is removed from the list.
- Added TON network configuration: new env var `VITE_TON_NETWORK` (`testnet` | `mainnet`, defaults to `testnet`). `PaymentPage` now specifies `network: CHAIN.TESTNET/MAINNET` in `sendTransaction`, checks connected wallet chain, shows wrong-network warning banner, and disables Pay button if wallet is on the wrong network.
