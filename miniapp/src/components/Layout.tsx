import { Outlet, useNavigate } from "react-router-dom";
import { BottomNav } from "./BottomNav";
import { ErrorBoundary } from "./ErrorBoundary";
import { OfflineBanner } from "./OfflineBanner";
import { Spinner } from "@telegram-tools/ui-kit";
import { useAuth } from "../contexts/AuthContext";
import { useOnlineStatus } from "../hooks/useOnlineStatus";

export function Layout() {
  const { isReady } = useAuth();
  const navigate = useNavigate();
  const online = useOnlineStatus();

  if (!isReady) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner size="32px" />
      </div>
    );
  }

  return (
    <div className="min-h-screen pb-16">
      <OfflineBanner />
      <div className={`mx-auto max-w-2xl px-4 py-4 transition-[padding] duration-300 ${!online ? "pt-12" : ""}`}>
        <ErrorBoundary onReset={() => navigate("/listings", { replace: true })}>
          <Outlet />
        </ErrorBoundary>
      </div>
      <BottomNav />
    </div>
  );
}
