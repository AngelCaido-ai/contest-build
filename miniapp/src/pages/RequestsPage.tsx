import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Text,
  Input,
  Button,
  Group,
  GroupItem,
  SkeletonElement,
} from "@telegram-tools/ui-kit";
import { usePaginatedApi } from "../hooks/usePaginatedApi";
import { EmptyState } from "../components/EmptyState";
import { Pagination } from "../components/Pagination";
import type { RequestItem } from "../types";

export function RequestsPage() {
  const navigate = useNavigate();

  const [budgetMin, setBudgetMin] = useState("");
  const [budgetMax, setBudgetMax] = useState("");

  const buildUrl = useCallback(
    (limit: number, offset: number) => {
      const params = new URLSearchParams();
      if (budgetMin) params.set("budget_min", budgetMin);
      if (budgetMax) params.set("budget_max", budgetMax);
      params.set("limit", String(limit));
      params.set("offset", String(offset));
      return `/requests?${params.toString()}`;
    },
    [budgetMin, budgetMax],
  );

  const {
    data: requests,
    loading,
    error,
    page,
    hasMore,
    nextPage,
    prevPage,
    resetPage,
    refetch,
  } = usePaginatedApi<RequestItem>(buildUrl, [budgetMin, budgetMax]);

  const handleApply = () => {
    resetPage();
    refetch();
  };

  return (
    <div className="flex flex-col gap-4">
      <Text type="title2" weight="bold">
        Advertiser Requests
      </Text>
      <Button text="Create Request" type="primary" onClick={() => navigate("/requests/new")} />

      <Group header="Filters">
        <div className="flex flex-col gap-2 px-4 py-2">
          <Input
            placeholder="Budget from"
            type="text"
            numeric
            value={budgetMin}
            onChange={(v) => setBudgetMin(v)}
          />
          <Input
            placeholder="Budget to"
            type="text"
            numeric
            value={budgetMax}
            onChange={(v) => setBudgetMax(v)}
          />
        </div>
        <div className="px-4 pb-3">
          <Button text="Apply" type="secondary" onClick={handleApply} />
        </div>
      </Group>

      {loading && (
        <Group>
          {[1, 2, 3].map((i) => (
            <GroupItem
              key={i}
              text={<SkeletonElement style={{ width: "60%", height: 16 }} />}
              description={<SkeletonElement style={{ width: "80%", height: 12 }} />}
            />
          ))}
        </Group>
      )}

      {!loading && error && (
        <EmptyState
          icon="⚠️"
          title="Loading error"
          description={error}
        />
      )}

      {!loading && !error && (!requests || requests.length === 0) && (
        <EmptyState
          icon="📝"
          title="No requests"
          description="Try adjusting the filters"
        />
      )}

      {!loading && requests && requests.length > 0 && (
        <Group header="Requests">
          {requests.map((item) => (
            <GroupItem
              key={item.id}
              text={
                item.budget != null
                  ? `Budget: $${item.budget}`
                  : "Budget not specified"
              }
              description={
                [
                  item.niche && `Niche: ${item.niche}`,
                  item.brief && item.brief.slice(0, 80),
                  item.languages?.length && `Languages: ${item.languages.join(", ")}`,
                ]
                  .filter(Boolean)
                  .join(" · ") || "No description"
              }
              after={<Button text="Respond" type="primary" onClick={() => navigate(`/requests/${item.id}`)} />}
              onClick={() => navigate(`/requests/${item.id}`)}
              chevron
            />
          ))}
        </Group>
      )}

      {!loading && <Pagination page={page} hasMore={hasMore} onPrev={prevPage} onNext={nextPage} />}
    </div>
  );
}
