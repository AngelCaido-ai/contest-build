# Current Plan (updated 2026-02-08)

## Competition Requirements Status

### A. Two-Sided Marketplace — DONE

| Requirement | Status | Where Implemented |
|---|---|---|
| Channel owner listings | DONE | backend API + bot `/create_listing` + miniapp |
| Advertiser requests | DONE | backend API + bot `/create_request` + miniapp |
| PR managers | DONE | bot `/add_manager`, `/list_managers`, `/remove_manager` + miniapp UI |
| Unified workflow (both entry points → single process) | DONE | backend `Deal` + bot `deals.py` |
| Negotiations via bot (not chat in miniapp) | PARTIAL | bot FSM + inline buttons; no free-form messaging |

### B. Verified Statistics — DONE

| Requirement | Status | Where Implemented |
|---|---|---|
| Subscribers | DONE | `stats_service.py` (Bot API fallback) |
| Average views / reach | DONE | `stats_service.py` (MTProto) |
| Language charts | DONE | `stats_service.py` (MTProto → `languages_json`) |
| Premium stats | DONE | `stats_service.py` (MTProto → `premium_json`) |
| Bot API fallback | DONE | `fetch_bot_api_subscribers()` |

### C. Ad Formats and Prices — DONE

| Requirement | Status | Where Implemented |
|---|---|---|
| Price by format | DONE | `Listing.format` (free field, default `post`) |
| Price in TON and USD | DONE | `Listing.price_ton`, `Listing.price_usd` |

### D. Escrow Deal + Lifecycle — DONE

| Requirement | Status | Where Implemented |
|---|---|---|
| Advertiser payment | DONE | `escrow_service.create_deposit` + `ton_escrow.create_deposit_wallet` |
| Fund holding | DONE | Custodial: separate wallet per deal |
| Auto-cancel/timeout | DONE | `check_payment_timeouts` (24h default) |
| Release (payout) | DONE | `escrow_service.release_payment` + `ton_escrow.send_payout` |
| Refund | DONE | `escrow_service.refund_payment` + `ton_escrow.send_refund` |
| Separate address per deal | DONE | `create_deposit_wallet` generates v4r2 wallet |
| Key encryption | DONE | AES-GCM via `ESCROW_SECRET_KEY` |
| 17 deal statuses | DONE | `DealStatus` enum + `ALLOWED_TRANSITIONS` |

### E. Creative Approval + Auto-Posting + Verification — DONE (negotiations PARTIAL)

| Requirement | Status | Where Implemented |
|---|---|---|
| Creative upload (text + media) | DONE | bot `/creative` + backend `Creative` model |
| Review / approve / edits | DONE | bot `/creative_status` + FSM |
| Creative negotiations | PARTIAL | only comment on reject, no free-form messaging |
| Auto-posting by `publish_at` | DONE | `process_scheduled_posts` task |
| Tamper detection (edits) | DONE | watcher bot (`edited_channel_post`) |
| Deletion detection | DONE | `check_deleted_posts` task (copy to log chat) |
| Verification window → release/refund | DONE | `check_verification_windows` task |

---

## Remaining Work

### Stage 1 — Bot UX: Deal Messaging and Input Convenience (CRITICAL)

Current issues:
- Creative discussion limited to single comment on reject
- No free-form messaging between parties
- Date/time input in ISO format
- No progress indication in multi-step forms

#### 1.1 Deal Messaging

Problem: by competition requirements negotiations must go through bot. Currently "negotiations" are only structured actions (terms, creative, status). No way to ask question, clarify brief, discuss details.

What's needed:

**Backend:**
- [x] Endpoint `POST /bot/deals/{id}/messages` — send deal message (DONE)
- [x] Endpoint `GET /bot/deals/{id}/messages` — get message history (DONE)

**Bot (`deals.py`):**
- [x] "Send message" button in `_deal_actions_keyboard` (DONE)
- [x] FSM `DealMessageState.content` (DONE)
- [x] "Message history" button (DONE)

#### 1.2 Convenient Date/Time Input

Current: user must enter `2026-02-05T18:30:00+03:00`. Inhuman.

**Bot (`deals.py`):**
- [ ] Quick selection buttons before input field
- [ ] Parse simple formats: `10.02 18:30`, `10.02.2026 18:30`
- [ ] Show confirmation after input
- [ ] Helper `_parse_datetime(text)`

#### 1.3 Progress Indication in Multi-Step Forms

**Bot (`deals.py`):**
- [ ] Add progress to prompt text
- [ ] Affected flows: DealTermsState, ListingCreateState, RequestCreateState, ListingRespondState, CreativeStatusState

### Stage 2 — Mini App: Full UI (CRITICAL)

Current: full UI on `@telegram-tools/ui-kit` with routing and 6 pages.

Sub-tasks:
- [x] Add `react-router-dom`, split App.tsx into pages
- [x] Integrate TonConnect
- [x] UI/UX improvements (loading, empty states, errors)
- [x] Channel stats display
- [x] "Go to bot" button
- [ ] Filters: subscribers, language (await API extension)
- [ ] Event history on deal page (awaits GET /deals/:id/events)

### Stage 3 — README and Documentation for Submission (CRITICAL)

- [ ] Update README: architecture diagram, deal status diagram, security, known limitations
- [ ] Update env.example
- [ ] Verify docker compose up --build runs all services

### Stage 4 — Test Bot Deployment (IMPORTANT)

- [ ] Deploy all services
- [ ] Configure webhooks
- [ ] Register Mini App via BotFather
- [ ] End-to-end test on testnet
- [ ] Record demo video

### Stage 5 — Stabilization and Tests (DESIRABLE)

- [ ] Run test cases from [test-cases.md](test-cases.md)
- [ ] Edge cases: double payment, parallel actions, invalid transitions
- [x] Rate limiting on escrow endpoints
- [ ] Verify MTProto stats with Telethon session

---

## Completed Stages

### ~~Stage 1 — Launch and Configuration~~ DONE
### ~~Stage 2 — Full Bot Workflow~~ DONE
### ~~Stage 3 — TON Escrow~~ DONE
### ~~Stage 4 — Creative and Auto-Posting~~ DONE
### ~~Stage 5 — Statistics~~ DONE

---

## Future Ideas

### Sweep Deposit Wallets via V5 Batch Actions
Use V5 batch to combine payout + sweep in single transaction.

### Remove V5 Support, Keep Only V4r2
Simplify code by dropping dual wallet support.

### CI/CD Setup
Automate build, tests, deploy via pipeline.

### Full V5 Migration (distant future)
When V5 ecosystem stabilizes — move all transactions to V5.
