import { useEffect, useRef } from "react";
import { Text, Button } from "@telegram-tools/ui-kit";

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onCancel]);

  if (!open) return null;

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === overlayRef.current) onCancel();
  };

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center px-6"
      style={{ backgroundColor: "rgba(0, 0, 0, 0.5)", backdropFilter: "blur(4px)" }}
      onClick={handleOverlayClick}
    >
      <div
        className="flex w-full max-w-sm flex-col gap-4 rounded-2xl p-5 shadow-xl"
        style={{
          backgroundColor: "var(--tg-theme-bg-color, #1c1c1e)",
          color: "var(--tg-theme-text-color, #fff)",
        }}
      >
        <Text type="title3" weight="bold">
          {title}
        </Text>
        {description && (
          <Text type="body" color="secondary">
            {description}
          </Text>
        )}
        <div className="flex gap-3 pt-1">
          <div className="flex-1">
            <Button text={cancelLabel} type="secondary" onClick={onCancel} />
          </div>
          <div className="flex-1">
            <Button text={confirmLabel} type="primary" onClick={onConfirm} />
          </div>
        </div>
      </div>
    </div>
  );
}
