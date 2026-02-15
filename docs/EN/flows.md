# System Flows

## Roles and Interaction Channels
- **Advertiser**: creates requests, pays for deals, approves creatives
- **Channel owner**: channel onboarding, listings, accepts deals, publishes
- **PR manager**: manages channel with granted permissions
- **Mini App**: catalog and forms
- **Bot**: negotiations, approval, notifications
- **Backend**: logic, statuses, audit, escrow
- **Jobs/Queue**: timeouts, auto-posting, verification

## Mini App Authentication
1. Mini App receives `initData` from Telegram WebApp.
2. Sends `initData` to API.
3. Backend validates signature and returns JWT.
4. Mini App stores token and uses it in requests.

## Channel Onboarding
1. Owner sends bot `/add_channel @channel` or `chat_id`.
2. Bot verifies user is channel admin.
3. Bot verifies its own rights in channel.
4. Bot API sends channel data to backend.
5. Channel is created or updated.

## Creating a Listing
1. Owner opens Mini App and selects channel.
2. Specifies price, format, and conditions.
3. Backend creates `Listing`.
4. Listing appears in catalog.

## Creating a Request
1. Advertiser fills brief and filters in Mini App.
2. Backend creates `Request`.
3. Channel owners see the request.

## Creating a Deal
### From listing
1. Advertiser selects listing.
2. Backend creates `Deal` with status `NEGOTIATING`.
3. Parties proceed to bot.

### From request
1. Owner responds to request.
2. Backend creates `Deal` with status `NEGOTIATING`.
3. Parties proceed to bot.

## Negotiations and Terms Lock
1. Price, format, and publish time are agreed in bot.
2. Bot locks terms and transitions to `TERMS_LOCKED`.
3. `DealEvent` is logged.

## Escrow and Payment
1. Advertiser receives deposit address.
2. After transaction confirmation status → `FUNDED`.
3. Payment event is logged.

## Creative and Approval
1. Advertiser sends brief/preferences.
2. Owner accepts or rejects.
3. When accepted, owner prepares creative and sends for review → `CREATIVE_REVIEW`.
4. Advertiser approves → `APPROVED` or returns for edits → `CREATIVE_DRAFT`.

## Auto-Posting
1. Scheduler checks `publish_at`.
2. Bot publishes post and saves `message_id`.
3. Deal transitions to `VERIFYING`.

## Delivery Verification
1. Any post edit → `tampered`.
2. Periodic job checks post availability.
3. After `verification_window`:
   - if `tampered` or `deleted` → `REFUNDED`
   - otherwise → `RELEASED`

## Deal Completion
- `RELEASED`: payout to channel owner
- `REFUNDED`: refund to advertiser
- `CANCELED`: cancellation due to timeout or refusal

## Timeouts
- `AWAITING_PAYMENT` older than `payment_timeout` → `CANCELED`

## Statistics Update
1. Owner can request stats refresh.
2. Backend tries MTProto `stats.getBroadcastStats`.
3. If MTProto unavailable → Bot API `getChatMemberCount`.
4. Data is saved to `ChannelStats`.
