# Changelog

## 2026-02-17

### backend
- **Fix:** При создании сделки из листинга цена теперь берётся из `price_usd` (приоритет) или `price_ton` (fallback). Ранее использовалось только `price_usd`, из-за чего если у листинга была указана только цена в TON, сделка создавалась без цены.

### bot
- **Feature:** Кнопка оплаты теперь открывает страницу оплаты в Mini App (`/deals/{id}/pay`) через `WebAppInfo`, если задана переменная `MINIAPP_URL`. Ранее формировались только внешние ссылки на TON-кошельки (`ton://transfer/...`, Tonkeeper). Старое поведение сохранено как fallback при отсутствии `MINIAPP_URL`.
- **Config:** Добавлена опциональная настройка `MINIAPP_URL` в `BotSettings`.
- **Fix:** Устранено дублирование сообщения о сделке. При отправке сообщения/креатива/статуса бот отправлял карточку сделки дважды: обычным сообщением и как новое закреплённое сообщение (если старое не удавалось отредактировать). Теперь `_refresh_active_deal_pin` только обновляет существующий пин, но не создаёт новый.

## 2026-02-16

### backend
- **Fix:** All `DateTime` columns converted to `DateTime(timezone=True)` across all models (`Deal`, `Channel`, `ChannelStats`, `Creative`, `DealEvent`, `EscrowPayment`, `Listing`, `Request`, `User`). This ensures Pydantic serializes datetimes with timezone info (`+00:00`), fixing a bug where the Mini App displayed times shifted by the user's UTC offset (e.g. 3 hours earlier for UTC+3 users).
- **Fix:** Replaced all `datetime.utcnow()` calls with `datetime.now(timezone.utc)` in models, services (`escrow_service.py`), tasks (`deal_tasks.py`), and routes (`stats.py`, `bot_actions.py`). `datetime.utcnow()` returns naive datetimes and is deprecated since Python 3.12.
- **Migration:** `0008_datetime_timezone_aware` — converts all DateTime columns to `TIMESTAMP WITH TIME ZONE`.
