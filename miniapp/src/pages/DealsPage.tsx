import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Text,
  Group,
  GroupItem,
  SkeletonElement,
  Select,
} from "@telegram-tools/ui-kit";
import { apiFetch } from "../api/client";
import { useApi } from "../hooks/useApi";
import { EmptyState } from "../components/EmptyState";
import { DealStatusBadge } from "../components/DealStatusBadge";
import type { Deal, DealStatus } from "../types";

const STATUS_OPTIONS = [
  { value: "__all__", label: "All statuses" },
  { value: "NEGOTIATING", label: "Negotiating" },
  { value: "TERMS_LOCKED", label: "Terms Locked" },
  { value: "AWAITING_PAYMENT", label: "Awaiting Payment" },
  { value: "FUNDED", label: "Funded" },
  { value: "CREATIVE_DRAFT", label: "Creative Draft" },
  { value: "CREATIVE_REVIEW", label: "Creative Review" },
  { value: "APPROVED", label: "Approved" },
  { value: "SCHEDULED", label: "Scheduled" },
  { value: "POSTED", label: "Posted" },
  { value: "VERIFYING", label: "Verifying" },
  { value: "RELEASED", label: "Released" },
  { value: "REFUNDED", label: "Refunded" },
  { value: "CANCELED", label: "Canceled" },
];

export function DealsPage() {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<string | null>("__all__");

  const fetcher = useCallback(() => apiFetch<Deal[]>("/deals"), []);
  const { data: deals, loading } = useApi(fetcher, []);

  const filtered =
    deals?.filter(
      (d) => !statusFilter || statusFilter === "__all__" || d.status === statusFilter,
    ) ?? [];

  return (
    <div className="flex flex-col gap-4">
      <Text type="title2" weight="bold">
        My Deals
      </Text>

      <Group header="Filter by Status">
        <div className="px-4 py-2">
          <Select
            options={STATUS_OPTIONS}
            value={statusFilter}
            onChange={(v) => setStatusFilter(v)}
          />
        </div>
      </Group>

      {loading && (
        <Group>
          {[1, 2, 3].map((i) => (
            <GroupItem
              key={i}
              text={<SkeletonElement style={{ width: "50%", height: 16 }} />}
              description={<SkeletonElement style={{ width: "30%", height: 12 }} />}
            />
          ))}
        </Group>
      )}

      {!loading && filtered.length === 0 && (
        <EmptyState
          icon="🤝"
          title="No deals"
          description="Create a deal through listings or requests"
        />
      )}

      {!loading && filtered.length > 0 && (
        <Group header="Deals">
          {filtered.map((deal) => (
            <GroupItem
              key={deal.id}
              text={`Deal #${deal.id}`}
              description={
                <div className="flex items-center gap-2">
                  <DealStatusBadge status={deal.status as DealStatus} />
                  {deal.price != null && (
                    <Text type="caption1" color="secondary">
                      ${deal.price}
                    </Text>
                  )}
                </div>
              }
              onClick={() => navigate(`/deals/${deal.id}`)}
              chevron
            />
          ))}
        </Group>
      )}
    </div>
  );
}
