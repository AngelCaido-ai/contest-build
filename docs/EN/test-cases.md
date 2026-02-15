# Test Cases

Format: ID — preconditions — steps — expected result.

## Mini App Authorization
- TC-AUTH-01 — valid `initData` — send `initData` to API — JWT and user profile received
- TC-AUTH-02 — invalid `initData` — send `initData` to API — 400 and validation error
- TC-AUTH-03 — `BOT_TOKEN` missing — send `initData` to API — 400 and rejection

## Channels and Managers
- TC-CH-01 — user is channel admin, bot in channel — `/add_channel` — channel created, `bot_admin_status` correct
- TC-CH-02 — user not admin — `/add_channel` — onboarding denied
- TC-CH-03 — bot not admin — `/add_channel` — channel created with `bot_admin_status=false`
- TC-CH-04 — repeated `/add_channel` — channel updated, rights updated
- TC-CH-05 — owner adds manager — create `ChannelManager` — record created

## Listings
- TC-LIST-01 — owner's channel exists — create listing — record created
- TC-LIST-02 — channel not owned by user — create listing — 404 or 403
- TC-LIST-03 — filter `active=true` — request — only active returned
- TC-LIST-04 — filter `price_min/price_max` — request — correct selection
- TC-LIST-05 — owner updates listing — PATCH — fields updated

## Requests
- TC-REQ-01 — authorized advertiser — create request — record created
- TC-REQ-02 — update request by non-owner — PATCH — 403
- TC-REQ-03 — filter `budget_min/budget_max` — request — correct selection

## Deals
- TC-DEAL-01 — create deal from listing — POST — status `NEGOTIATING`
- TC-DEAL-02 — create deal from request without `channel_id` — POST — 400
- TC-DEAL-03 — create deal from request by channel owner — POST — status `NEGOTIATING`
- TC-DEAL-04 — get deal by party — GET — access granted
- TC-DEAL-05 — get deal by stranger — GET — 403

## Terms and Statuses
- TC-TERM-01 — bot locks terms — `/bot/deals/{id}/terms` — status `TERMS_LOCKED`
- TC-TERM-02 — bot changes status via valid transition — `/bot/deals/{id}/status` — status updated
- TC-TERM-03 — invalid status transition — `/bot/deals/{id}/status` — 400

## Escrow
- TC-ESC-01 — status `TERMS_LOCKED` — create deposit — address created, status `AWAITING_PAYMENT`
- TC-ESC-02 — repeat deposit request — existing address returned
- TC-ESC-03 — bot confirms payment — status `FUNDED`, `confirmed_at` set

## Creative
- TC-CR-01 — create text creative — `/bot/deals/{id}/creative` — `CREATIVE_REVIEW`
- TC-CR-02 — create creative with media — `media_file_ids` populated
- TC-CR-03 — set status to `DRAFT` — deal `CREATIVE_DRAFT`
- TC-CR-04 — set status to `APPROVED` — deal `APPROVED`

## Auto-Posting and Verification
- TC-POST-01 — `publish_at` reached, creative present — job publishes post — `posted_message_id` saved
- TC-POST-02 — no creative text — job skips publication
- TC-VER-01 — `edited_channel_post` received — `tampered=true`
- TC-VER-02 — post unavailable when copying — `deleted=true`
- TC-VER-03 — verification window passed, no tamper/delete — status `RELEASED`
- TC-VER-04 — window passed, tamper/delete=true — status `REFUNDED`

## Timeouts
- TC-TIME-01 — `AWAITING_PAYMENT` older than timeout — status `CANCELED`

## Statistics
- TC-STAT-01 — MTProto configured — refresh stats — `languages` and `premium` populated
- TC-STAT-02 — MTProto unavailable — Bot API fallback — `subscribers` populated, `source=bot_api`
- TC-STAT-03 — user not owner — refresh stats — 404

## Mini App UI
- TC-UI-01 — load listings — list displayed
- TC-UI-02 — create request — status "created"
- TC-UI-03 — "Go to bot" button — opens bot link

## Security
- TC-SEC-01 — `X-Bot-Secret` missing — access to `/bot/*` denied
