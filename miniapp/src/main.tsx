import ReactDOM from "react-dom/client";
import { TonConnectUIProvider } from "@tonconnect/ui-react";
import { ThemeProvider, ToastProvider } from "@telegram-tools/ui-kit";
import "@telegram-tools/ui-kit/dist/index.css";

import App from "./App";
import "./index.css";

const manifestUrl = `${window.location.origin}/tonconnect-manifest.json`;

const root = document.getElementById("root");
if (root) {
  ReactDOM.createRoot(root).render(
    <ThemeProvider>
      <TonConnectUIProvider manifestUrl={manifestUrl}>
        <ToastProvider>
          <App />
        </ToastProvider>
      </TonConnectUIProvider>
    </ThemeProvider>,
  );
}
