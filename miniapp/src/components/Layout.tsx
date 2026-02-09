import { Outlet } from "react-router-dom";
import { BottomNav } from "./BottomNav";
import { Spinner } from "@telegram-tools/ui-kit";
import { useAuth } from "../contexts/AuthContext";

export function Layout() {
  const { isReady } = useAuth();

  if (!isReady) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner size="32px" />
      </div>
    );
  }

  return (
    <div className="min-h-screen pb-16">
      <div className="mx-auto max-w-2xl px-4 py-4">
        <Outlet />
      </div>
      <BottomNav />
    </div>
  );
}
