import { useState, useEffect } from "react";
import { useOnlineStatus } from "../hooks/useOnlineStatus";

export function OfflineBanner() {
  const online = useOnlineStatus();
  const [showReconnected, setShowReconnected] = useState(false);
  const [wasOffline, setWasOffline] = useState(false);

  useEffect(() => {
    if (!online) {
      setWasOffline(true);
      setShowReconnected(false);
      return;
    }

    if (wasOffline) {
      setShowReconnected(true);
      const timer = setTimeout(() => {
        setShowReconnected(false);
        setWasOffline(false);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [online, wasOffline]);

  if (online && !showReconnected) return null;

  return (
    <div
      className="fixed inset-x-0 top-0 z-50 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-white transition-colors duration-300"
      style={{
        backgroundColor: online ? "#22c55e" : "#ef4444",
      }}
    >
      <span>{online ? "Connection restored" : "No internet connection"}</span>
    </div>
  );
}
