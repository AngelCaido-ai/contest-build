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
  { value: "__all__", label: "Все статусы" },
  { value: "NEGOTIATING", label: "Переговоры" },
  { value: "TERMS_LOCKED", label: "Условия согласованы" },
  { value: "AWAITING_PAYMENT", label: "Ожидание оплаты" },
  { value: "FUNDED", label: "Оплачено" },
  { value: "CREATIVE_DRAFT", label: "Черновик креатива" },
  { value: "CREATIVE_REVIEW", label: "Ревью креатива" },
  { value: "APPROVED", label: "Одобрено" },
  { value: "SCHEDULED", label: "Запланировано" },
  { value: "POSTED", label: "Опубликовано" },
  { value: "VERIFYING", label: "Проверка" },
  { value: "RELEASED", label: "Завершено" },
  { value: "REFUNDED", label: "Возврат" },
  { value: "CANCELED", label: "Отменено" },
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
        Мои сделки
      </Text>

      <Group header="Фильтр по статусу">
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
          title="Нет сделок"
          description="Создайте сделку через каталог или заявки"
        />
      )}

      {!loading && filtered.length > 0 && (
        <Group header="Сделки">
          {filtered.map((deal) => (
            <GroupItem
              key={deal.id}
              text={`Сделка #${deal.id}`}
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
