# Тест-кейсы

Формат: ID — предусловия — шаги — ожидаемый результат.

## Авторизация Mini App
- TC-AUTH-01 — валидный `initData` — отправить `initData` в API — получен JWT и профиль пользователя
- TC-AUTH-02 — невалидный `initData` — отправить `initData` в API — 400 и ошибка проверки
- TC-AUTH-03 — отсутствует `BOT_TOKEN` — отправить `initData` в API — 400 и отказ

## Каналы и менеджеры
- TC-CH-01 — пользователь админ канала, бот в канале — `/add_channel` — канал создан, `bot_admin_status` корректный
- TC-CH-02 — пользователь не админ — `/add_channel` — отказ в онбординге
- TC-CH-03 — бот не админ — `/add_channel` — канал создан с `bot_admin_status=false`
- TC-CH-04 — повторный `/add_channel` — канал обновлён, права обновлены
- TC-CH-05 — владелец добавляет менеджера — создать `ChannelManager` — запись создана

## Listings
- TC-LIST-01 — канал владельца существует — создать listing — создана запись
- TC-LIST-02 — канал не принадлежит пользователю — создать listing — 404 или 403
- TC-LIST-03 — фильтр `active=true` — запрос — возвращаются только активные
- TC-LIST-04 — фильтр `price_min/price_max` — запрос — корректная выборка
- TC-LIST-05 — обновление listing владельцем — PATCH — поля обновлены

## Requests
- TC-REQ-01 — авторизованный рекламодатель — создать request — запись создана
- TC-REQ-02 — обновление request не владельцем — PATCH — 403
- TC-REQ-03 — фильтр `budget_min/ budget_max` — запрос — корректная выборка

## Сделки
- TC-DEAL-01 — создать deal из listing — POST — статус `NEGOTIATING`
- TC-DEAL-02 — создать deal из request без `channel_id` — POST — 400
- TC-DEAL-03 — создать deal из request владельцем канала — POST — статус `NEGOTIATING`
- TC-DEAL-04 — получить сделку стороной — GET — доступ разрешён
- TC-DEAL-05 — получить сделку посторонним — GET — 403

## Terms и статусы
- TC-TERM-01 — бот фиксирует terms — `/bot/deals/{id}/terms` — статус `TERMS_LOCKED`
- TC-TERM-02 — бот меняет статус по валидному переходу — `/bot/deals/{id}/status` — статус обновлён
- TC-TERM-03 — недопустимый переход статуса — `/bot/deals/{id}/status` — 400

## Эскроу
- TC-ESC-01 — статус `TERMS_LOCKED` — создание депозита — адрес создан, статус `AWAITING_PAYMENT`
- TC-ESC-02 — повторный запрос депозита — возвращается существующий адрес
- TC-ESC-03 — подтверждение оплаты ботом — статус `FUNDED`, `confirmed_at` установлен

## Креатив
- TC-CR-01 — создание текстового креатива — `/bot/deals/{id}/creative` — `CREATIVE_REVIEW`
- TC-CR-02 — создание креатива с media — `media_file_ids` заполнен
- TC-CR-03 — смена статуса на `DRAFT` — сделка `CREATIVE_DRAFT`
- TC-CR-04 — смена статуса на `APPROVED` — сделка `APPROVED`

## Автопостинг и верификация
- TC-POST-01 — `publish_at` наступил, креатив есть — job публикует пост — `posted_message_id` сохранён
- TC-POST-02 — нет текста креатива — job пропускает публикацию
- TC-VER-01 — получен `edited_channel_post` — `tampered=true`
- TC-VER-02 — пост недоступен при копировании — `deleted=true`
- TC-VER-03 — окно верификации прошло, без tamper/delete — статус `RELEASED`
- TC-VER-04 — окно прошло, tamper/delete=true — статус `REFUNDED`

## Таймауты
- TC-TIME-01 — `AWAITING_PAYMENT` старше таймаута — статус `CANCELED`

## Статистика
- TC-STAT-01 — MTProto настроен — refresh stats — поля `languages` и `premium` заполнены
- TC-STAT-02 — MTProto недоступен — fallback Bot API — `subscribers` заполнен, `source=bot_api`
- TC-STAT-03 — пользователь не владелец — refresh stats — 404

## Mini App UI
- TC-UI-01 — загрузка listings — отображается список
- TC-UI-02 — создание request — статус “created”
- TC-UI-03 — кнопка “Go to bot” — открывает ссылку на бота

## Безопасность
- TC-SEC-01 — отсутствует `X-Bot-Secret` — доступ к `/bot/*` запрещён
