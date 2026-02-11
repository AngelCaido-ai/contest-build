import { useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Button,
  Group,
  GroupItem,
  Spinner,
  Text,
  useToast,
} from "@telegram-tools/ui-kit";
import { apiFetch } from "../api/client";
import { useApi } from "../hooks/useApi";
import { useBackButton } from "../hooks/useBackButton";
import type { ListingDetail } from "../types";

function formatNumber(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("ru-RU").format(value);
}

function formatMaybeJson(value: unknown): string {
  if (value == null) return "—";
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return "—";
  }
}

export function ListingDetailPage() {
  useBackButton();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();

  const listingId = Number(id);
  const fetcher = useCallback(() => apiFetch<ListingDetail>(`/listings/${listingId}`), [listingId]);
  const { data: listing, loading, error } = useApi(fetcher, [listingId]);

  const channel = listing?.channel ?? null;
  const stats = channel?.stats ?? null;

  const respond = async () => {
    if (!listing) return;
    try {
      const deal = await apiFetch<{ id: number }>("/deals", {
        method: "POST",
        body: JSON.stringify({ listing_id: listing.id, channel_id: listing.channel_id }),
      });
      showToast("Сделка создана", { type: "success" });
      navigate(`/deals/${deal.id}`);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка", { type: "error" });
    }
  };

  if (!id || Number.isNaN(listingId)) {
    return (
      <div className="flex flex-col items-center gap-3 py-12">
        <Text type="body" color="danger">Некорректный листинг</Text>
        <Button text="Назад" type="secondary" onClick={() => navigate(-1)} />
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner size="32px" />
      </div>
    );
  }

  if (error || !listing) {
    return (
      <div className="flex flex-col items-center gap-3 py-12">
        <Text type="body" color="danger">{error ?? "Листинг не найден"}</Text>
        <Button text="Назад" type="secondary" onClick={() => navigate(-1)} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Text type="title2" weight="bold">
        Предпросмотр
      </Text>

      <Group header="Канал">
        <GroupItem
          text={channel?.title ?? (channel?.username ? `@${channel.username}` : `Канал #${listing.channel_id}`)}
          description={channel?.username ? `@${channel.username}` : "—"}
        />
      </Group>

      <Group header="Статистика">
        <GroupItem
          text="Подписчики"
          after={<Text type="body">{formatNumber(stats?.subscribers ?? null)}</Text>}
        />
        <GroupItem
          text="Просмотры на пост"
          after={<Text type="body">{formatNumber(stats?.views_per_post ?? null)}</Text>}
        />
        <GroupItem
          text="Источник"
          after={<Text type="body">{stats?.source ?? "—"}</Text>}
        />
      </Group>

      <Group header="Условия">
        <GroupItem
          text="Цена (USD)"
          after={<Text type="body">{listing.price_usd != null ? `$${listing.price_usd}` : "—"}</Text>}
        />
        <GroupItem
          text="Цена (TON)"
          after={<Text type="body">{listing.price_ton != null ? `${listing.price_ton}` : "—"}</Text>}
        />
        <GroupItem text="Формат" after={<Text type="body">{listing.format}</Text>} />
        <GroupItem
          text="Категории"
          after={
            <Text type="body">
              {listing.categories?.length ? listing.categories.join(", ") : "—"}
            </Text>
          }
        />
      </Group>

      <Group header="Ограничения">
        <div className="px-4 py-3">
          <Text type="body" color="secondary">
            {formatMaybeJson(listing.constraints)}
          </Text>
        </div>
      </Group>

      <div className="flex flex-col gap-2 pt-2">
        <Button text="Откликнуться" type="primary" onClick={respond} />
        <Button text="Назад" type="secondary" onClick={() => navigate(-1)} />
      </div>
    </div>
  );
}
