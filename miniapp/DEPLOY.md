# Деплой Frontend на GitHub Pages

## Быстрый старт

1. **Включите GitHub Pages** в настройках репозитория:
   - Перейдите в Settings → Pages
   - В разделе "Source" выберите "GitHub Actions"

2. **Настройте Secrets** (Settings → Secrets and variables → Actions):
   - `VITE_API_BASE` - URL вашего API бэкенда (например, `https://api.example.com`)
   - `VITE_BOT_URL` - URL вашего Telegram бота (например, `https://t.me/your_bot`)
   - `VITE_BASE_PATH` - базовый путь для GitHub Pages:
     - Если репозиторий называется `contest`: `/contest/`
     - Если репозиторий называется `username.github.io`: `/`
     - Или используйте имя вашего репозитория: `/<repository-name>/`

3. **Запушьте изменения** в ветку `main`:
   ```bash
   git add .
   git commit -m "Setup GitHub Pages deployment"
   git push origin main
   ```

4. **Проверьте деплой**:
   - Перейдите в Actions → Deploy Frontend to GitHub Pages
   - После успешного выполнения приложение будет доступно по адресу:
     `https://<username>.github.io/<repository-name>/`

## Локальная сборка

Для проверки сборки локально:

```bash
cd miniapp
npm install
npm run build
npm run preview
```

## Переменные окружения

- `VITE_API_BASE` - базовый URL API (обязательно для production)
- `VITE_BOT_URL` - URL Telegram бота (обязательно для production)
- `VITE_BASE_PATH` - базовый путь для роутинга (опционально, по умолчанию `/contest/` в production)

## Troubleshooting

- Если приложение не загружается, проверьте `VITE_BASE_PATH` - он должен соответствовать пути репозитория
- Если API запросы не работают, проверьте `VITE_API_BASE` и CORS настройки на бэкенде
- Убедитесь, что GitHub Pages включен в настройках репозитория
