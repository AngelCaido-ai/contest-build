import "vite/client";

declare global {
  interface ImportMetaEnv {
    readonly BASE_URL: string;
    readonly VITE_API_BASE?: string;
    readonly VITE_BOT_URL?: string;
    readonly VITE_TON_NETWORK?: "testnet" | "mainnet";
  }

  interface ImportMeta {
    readonly env: ImportMetaEnv;
  }

  interface TelegramWebAppThemeParams {
    bg_color?: string;
    text_color?: string;
    hint_color?: string;
    link_color?: string;
    button_color?: string;
    button_text_color?: string;
    secondary_bg_color?: string;
    header_bg_color?: string;
    accent_text_color?: string;
    section_bg_color?: string;
    section_header_text_color?: string;
    subtitle_text_color?: string;
    destructive_text_color?: string;
  }

  interface TelegramWebAppBackButton {
    isVisible: boolean;
    show: () => void;
    hide: () => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
  }

  interface TelegramWebApp {
    initData: string;
    ready: () => void;
    openTelegramLink: (url: string) => void;
    colorScheme: "light" | "dark";
    themeParams: TelegramWebAppThemeParams;
    BackButton: TelegramWebAppBackButton;
    close: () => void;
    expand: () => void;
  }

  interface Telegram {
    WebApp: TelegramWebApp;
  }

  interface Window {
    Telegram?: Telegram;
  }
}

export {};
