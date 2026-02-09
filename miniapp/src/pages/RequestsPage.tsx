import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Text,
  Input,
  Button,
  Group,
  GroupItem,
  SkeletonElement,
  useToast,
} from "@telegram-tools/ui-kit";
import { apiFetch } from "../api/client";
import { useApi } from "../hooks/useApi";
import { EmptyState } from "../components/EmptyState";
import type { RequestItem } from "../types";

export function RequestsPage() {
  const { showToast } = useToast();
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

  const { data: requests, loading, refetch } = useApi(fetcher, [budgetMin, budgetMax]);

  const respondToRequest = async (requestId: number) => {
    try {
      const deal = await apiFetch<{ id: number }>("/deals", {
        method: "POST",
        body: JSON.stringify({ request_id: requestId }),
      });
      showToast("Сделка создана", { type: "success" });
      navigate(`/deals/${deal.id}`);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка", { type: "error" });
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Text type="title2" weight="bold">
        Заявки рекламодателей
      </Text>

      <Group header="Фильтры">
        <div className="flex gap-2 px-4 py-2">
          <Input
            placeholder="Бюджет от"
            type="text"
            numeric
            value={budgetMin}
            onChange={(v) => setBudgetMin(v)}
          />
          <Input
            placeholder="Бюджет до"
            type="text"
            numeric
            value={budgetMax}
            onChange={(v) => setBudgetMax(v)}
          />
        </div>
        <div className="px-4 pb-3">
          <Button text="Применить" type="secondary" onClick={refetch} />
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

      {!loading && (!requests || requests.length === 0) && (
        <EmptyState
          icon="📝"
          title="Нет заявок"
          description="Попробуйте изменить фильтры"
        />
      )}

      {!loading && requests && requests.length > 0 && (
        <Group header="Заявки">
          {requests.map((item) => (
            <GroupItem
              key={item.id}
              text={
                item.budget != null
                  ? `Бюджет: $${item.budget}`
                  : "Бюджет не указан"
              }
              description={
                [
                  item.niche && `Ниша: ${item.niche}`,
                  item.brief && item.brief.slice(0, 80),
                  item.languages?.length && `Языки: ${item.languages.join(", ")}`,
                ]
                  .filter(Boolean)
                  .join(" · ") || "Без описания"
              }
              after={
                <Button
                  text="Откликнуться"
                  type="primary"
                  onClick={() => respondToRequest(item.id)}
                />
              }
              chevron
            />
          ))}
        </Group>
      )}
    </div>
  );
}
