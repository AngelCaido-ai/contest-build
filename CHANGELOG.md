# Changelog

## 2026-02-16

### backend
- **Fix:** All `DateTime` columns converted to `DateTime(timezone=True)` across all models (`Deal`, `Channel`, `ChannelStats`, `Creative`, `DealEvent`, `EscrowPayment`, `Listing`, `Request`, `User`). This ensures Pydantic serializes datetimes with timezone info (`+00:00`), fixing a bug where the Mini App displayed times shifted by the user's UTC offset (e.g. 3 hours earlier for UTC+3 users).
- **Fix:** Replaced all `datetime.utcnow()` calls with `datetime.now(timezone.utc)` in models, services (`escrow_service.py`), tasks (`deal_tasks.py`), and routes (`stats.py`, `bot_actions.py`). `datetime.utcnow()` returns naive datetimes and is deprecated since Python 3.12.
- **Migration:** `0008_datetime_timezone_aware` — converts all DateTime columns to `TIMESTAMP WITH TIME ZONE`.
