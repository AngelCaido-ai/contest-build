import { Text } from "@telegram-tools/ui-kit";
import type { DealStatus } from "../types";

const statusConfig: Record<DealStatus, { label: string; color: string }> = {
  NEGOTIATING: { label: "Negotiating", color: "#3b82f6" },
  TERMS_LOCKED: { label: "Terms Locked", color: "#6366f1" },
  AWAITING_PAYMENT: { label: "Awaiting Payment", color: "#f59e0b" },
  FUNDED: { label: "Funded", color: "#10b981" },
  CREATIVE_DRAFT: { label: "Creative Draft", color: "#8b5cf6" },
  CREATIVE_REVIEW: { label: "Creative Review", color: "#a855f7" },
  APPROVED: { label: "Approved", color: "#22c55e" },
  SCHEDULED: { label: "Scheduled", color: "#06b6d4" },
  POSTED: { label: "Posted", color: "#14b8a6" },
  VERIFYING: { label: "Verifying", color: "#eab308" },
  RELEASED: { label: "Released", color: "#22c55e" },
  REFUNDED: { label: "Refunded", color: "#ef4444" },
  CANCELED: { label: "Canceled", color: "#6b7280" },
};

type Props = {
  status: DealStatus;
};

export function DealStatusBadge({ status }: Props) {
  const config = statusConfig[status] ?? { label: status, color: "#6b7280" };

  return (
    <span
      className="inline-flex items-center rounded-full px-2.5 py-0.5"
      style={{ backgroundColor: config.color + "1a", color: config.color }}
    >
      <Text type="caption1" weight="medium">
        {config.label}
      </Text>
    </span>
  );
}
