import ReactDOM from "react-dom/client";
import { TonConnectUIProvider } from "@tonconnect/ui-react";
import { ThemeProvider, ToastProvider } from "@telegram-tools/ui-kit";
import "@telegram-tools/ui-kit/dist/index.css";

import App from "./App";
import "./index.css";
import {
  ErrorBoundary,
  GlobalErrorFallback,
} from "./components/ErrorBoundary";

const manifestUrl = new URL(
  "tonconnect-manifest.json",
  `${window.location.origin}${import.meta.env.BASE_URL}`,
).toString();

const root = document.getElementById("root");
if (root) {
  ReactDOM.createRoot(root).render(
    <ErrorBoundary fallback={<GlobalErrorFallback />}>
      <ThemeProvider>
        <TonConnectUIProvider manifestUrl={manifestUrl}>
          <ToastProvider>
            <App />
          </ToastProvider>
        </TonConnectUIProvider>
      </ThemeProvider>
    </ErrorBoundary>,
  );
}
