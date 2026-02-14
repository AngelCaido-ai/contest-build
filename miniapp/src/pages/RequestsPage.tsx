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
import { apiFetch } from "../api/client";
import { useApi } from "../hooks/useApi";
import { EmptyState } from "../components/EmptyState";
import type { RequestItem } from "../types";

export function RequestsPage() {
  const navigate = useNavigate();

  const [budgetMin, setBudgetMin] = useState("");
  const [budgetMax, setBudgetMax] = useState("");

  const fetcher = useCallback(() => {
    const params = new URLSearchParams();
    if (budgetMin) params.set("budget_min", budgetMin);
    if (budgetMax) params.set("budget_max", budgetMax);
    const qs = params.toString();
    return apiFetch<RequestItem[]>(`/requests${qs ? `?${qs}` : ""}`);
  }, [budgetMin, budgetMax]);

  const { data: requests, loading, error, refetch } = useApi(fetcher, [budgetMin, budgetMax]);

  return (
    <div className="flex flex-col gap-4">
      <Text type="title2" weight="bold">
        Advertiser Requests
      </Text>
      <Button text="Create Request" type="primary" onClick={() => navigate("/requests/new")} />

      <Group header="Filters">
        <div className="flex gap-2 px-4 py-2">
          <div className="min-w-0 flex-1">
            <Input
              placeholder="Budget from"
              type="text"
              numeric
              value={budgetMin}
              onChange={(v) => setBudgetMin(v)}
            />
          </div>
          <div className="min-w-0 flex-1">
            <Input
              placeholder="Budget to"
              type="text"
              numeric
              value={budgetMax}
              onChange={(v) => setBudgetMax(v)}
            />
          </div>
        </div>
        <div className="px-4 pb-3">
          <Button text="Apply" type="secondary" onClick={refetch} />
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
    </div>
  );
}
