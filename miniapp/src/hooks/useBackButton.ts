import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

export function useBackButton(enabled = true) {
  const navigate = useNavigate();

  useEffect(() => {
    const bb = window.Telegram?.WebApp?.BackButton;
    if (!bb) return;

    if (!enabled) {
      bb.hide();
      return;
    }

    const handler = () => navigate(-1);
    bb.show();
    bb.onClick(handler);

    return () => {
      bb.offClick(handler);
      bb.hide();
    };
  }, [enabled, navigate]);
}
