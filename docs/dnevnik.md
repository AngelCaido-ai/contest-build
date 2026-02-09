# Dnevnik

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
- Полная перестройка Mini App: монолитный App.tsx разбит на 6 страниц с роутингом (react-router-dom HashRouter).
- Перешли на UI-библиотеку `@telegram-tools/ui-kit` (ThemeProvider, Button, Input, Group, GroupItem, Text, Select, Toast, SkeletonElement, Spinner).
- Удалены кастомные shadcn-компоненты (button.tsx, card.tsx, input.tsx) — заменены на ui-kit.
- Добавлены страницы: ListingsPage, RequestsPage, ChannelsPage, DealsPage, DealDetailPage, PaymentPage.
- Добавлен AuthContext — централизованная аутентификация через Telegram initData + JWT.
- Добавлен API-клиент (api/client.ts) с типизированным apiFetch<T>.
- Добавлен универсальный хук useApi<T> (data, loading, error, refetch).
- Добавлен хук useBackButton для интеграции с Telegram BackButton.
- Добавлен DealStatusBadge — цветной бейдж по статусу сделки (13 статусов).
- Добавлен EmptyState — компонент пустого состояния.
- Добавлен Layout с bottom tab навигацией (4 таба: Каталог, Заявки, Каналы, Сделки).
- Интегрирован TonConnect (@tonconnect/ui-react): подключение кошелька, отправка транзакций.
- Добавлена PaymentPage: QR-код депозитного адреса, кнопка TonConnect Pay.
- Типы данных вынесены в types/index.ts (Listing, RequestItem, Deal, Channel, Manager, DealEvent, EscrowPayment, User, DealStatus).
- Расширен env.d.ts: themeParams, BackButton, colorScheme.
- Новые зависимости: react-router-dom, @telegram-tools/ui-kit, @tonconnect/ui-react, qrcode.react.
