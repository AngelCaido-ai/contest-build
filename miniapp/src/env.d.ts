interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_BOT_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

interface TelegramWebApp {
  initData: string;
  ready: () => void;
  openTelegramLink: (url: string) => void;
}

interface Telegram {
  WebApp: TelegramWebApp;
}

interface Window {
  Telegram?: Telegram;
}
