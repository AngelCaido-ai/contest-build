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
import type { Listing } from "../types";

export function ListingsPage() {
  const navigate = useNavigate();

  const [priceMin, setPriceMin] = useState("");
  const [priceMax, setPriceMax] = useState("");

  const fetcher = useCallback(() => {
    const params = new URLSearchParams();
    if (priceMin) params.set("price_min", priceMin);
    if (priceMax) params.set("price_max", priceMax);
    params.set("active", "true");
    params.set("exclude_own", "true");
    const qs = params.toString();
    return apiFetch<Listing[]>(`/listings${qs ? `?${qs}` : ""}`);
  }, [priceMin, priceMax]);

  const { data: listings, loading, refetch } = useApi(fetcher, [priceMin, priceMax]);

  return (
    <div className="flex flex-col gap-4">
      <Text type="title2" weight="bold">
        Каталог размещений
      </Text>

      <Group header="Фильтры">
        <div className="flex gap-2 px-4 py-2">
          <div className="min-w-0 flex-1">
            <Input
              placeholder="Цена от"
              type="text"
              numeric
              value={priceMin}
              onChange={(v) => setPriceMin(v)}
            />
          </div>
          <div className="min-w-0 flex-1">
            <Input
              placeholder="Цена до"
              type="text"
              numeric
              value={priceMax}
              onChange={(v) => setPriceMax(v)}
            />
          </div>
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
              description={<SkeletonElement style={{ width: "40%", height: 12 }} />}
            />
          ))}
        </Group>
      )}

      {!loading && (!listings || listings.length === 0) && (
        <EmptyState
          icon="📋"
          title="Нет размещений"
          description="Попробуйте изменить фильтры"
        />
      )}

      {!loading && listings && listings.length > 0 && (
        <Group header="Размещения">
          {listings.map((item) => (
            <GroupItem
              key={item.id}
              text={`Канал #${item.channel_id}`}
              description={`${item.price_usd != null ? `$${item.price_usd}` : "Цена не указана"} · ${item.format}`}
              onClick={() => navigate(`/listings/${item.id}`)}
              chevron
            />
          ))}
        </Group>
      )}
    </div>
  );
}
