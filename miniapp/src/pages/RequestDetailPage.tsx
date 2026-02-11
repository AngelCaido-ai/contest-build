import { useCallback, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Button,
  Group,
  GroupItem,
  Select,
  Spinner,
  Text,
  useToast,
} from "@telegram-tools/ui-kit";
import { apiFetch } from "../api/client";
import { useApi } from "../hooks/useApi";
import { useBackButton } from "../hooks/useBackButton";
import type { Channel, RequestItem } from "../types";

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

export function RequestDetailPage() {
  useBackButton();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();

  const requestId = Number(id);
  const fetchRequest = useCallback(() => apiFetch<RequestItem>(`/requests/${requestId}`), [requestId]);
  const { data: request, loading: requestLoading, error: requestError } = useApi(fetchRequest, [requestId]);

  const fetchChannels = useCallback(() => apiFetch<Channel[]>("/channels"), []);
  const {
    data: channels,
    loading: channelsLoading,
    error: channelsError,
    refetch: refetchChannels,
  } = useApi(fetchChannels, []);

  const [selectedChannelId, setSelectedChannelId] = useState<string | null>(null);

  const selectedChannel = useMemo(() => {
    if (!channels || channels.length === 0) return null;
    const picked = selectedChannelId ? Number(selectedChannelId) : null;
    if (picked != null && !Number.isNaN(picked)) {
      return channels.find((c) => c.id === picked) ?? null;
    }
    return channels[0] ?? null;
  }, [channels, selectedChannelId]);

  const channelOptions = useMemo(() => {
    return (
      channels?.map((c) => ({
        value: String(c.id),
        label: c.title ?? (c.username ? `@${c.username}` : `#${c.tg_chat_id}`),
      })) ?? []
    );
  }, [channels]);

  const refreshStats = async () => {
    if (!selectedChannel) return;
    try {
      await apiFetch(`/stats/channels/${selectedChannel.id}/refresh`, { method: "POST" });
      showToast("Статистика обновлена", { type: "success" });
      refetchChannels();
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка", { type: "error" });
    }
  };

  const respond = async () => {
    if (!request || !selectedChannel) {
      showToast("Выберите канал", { type: "error" });
      return;
    }
    try {
      const deal = await apiFetch<{ id: number }>("/deals", {
        method: "POST",
        body: JSON.stringify({ request_id: request.id, channel_id: selectedChannel.id }),
      });
      showToast("Сделка создана", { type: "success" });
      navigate(`/deals/${deal.id}`);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка", { type: "error" });
    }
  };

  if (!id || Number.isNaN(requestId)) {
    return (
      <div className="flex flex-col items-center gap-3 py-12">
        <Text type="body" color="danger">Некорректная заявка</Text>
        <Button text="Назад" type="secondary" onClick={() => navigate(-1)} />
      </div>
    );
  }

  if (requestLoading || channelsLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner size="32px" />
      </div>
    );
  }

  if (requestError || !request) {
    return (
      <div className="flex flex-col items-center gap-3 py-12">
        <Text type="body" color="danger">{requestError ?? "Заявка не найдена"}</Text>
        <Button text="Назад" type="secondary" onClick={() => navigate(-1)} />
      </div>
    );
  }

  if (channelsError || !channels || channels.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 py-12">
        <Text type="body" color="danger">
          {channelsError ?? "Сначала добавьте канал"}
        </Text>
        <Button text="Назад" type="secondary" onClick={() => navigate(-1)} />
      </div>
    );
  }

  const stats = selectedChannel?.stats ?? null;

  return (
    <div className="flex flex-col gap-4">
      <Text type="title2" weight="bold">
        Предпросмотр
      </Text>

      <Group header="Канал">
        <div className="px-4 py-2">
          <Select
            options={channelOptions}
            value={selectedChannelId ?? String((selectedChannel ?? channels[0]).id)}
            onChange={(v) => setSelectedChannelId(v)}
          />
        </div>
        <GroupItem
          text="Статистика"
          description={
            stats
              ? `${formatNumber(stats.subscribers)} подписчиков · ${formatNumber(stats.views_per_post)} просмотров`
              : "Статистика не загружена"
          }
          after={<Button text="Обновить" type="secondary" onClick={refreshStats} />}
        />
      </Group>

      <Group header="Условия заявки">
        <GroupItem
          text="Бюджет"
          after={<Text type="body">{request.budget != null ? `$${request.budget}` : "—"}</Text>}
        />
        <GroupItem
          text="Ниша"
          after={<Text type="body">{request.niche ?? "—"}</Text>}
        />
        <GroupItem
          text="Языки"
          after={<Text type="body">{request.languages?.length ? request.languages.join(", ") : "—"}</Text>}
        />
        <GroupItem
          text="Мин. подписчики"
          after={<Text type="body">{formatNumber(request.min_subs)}</Text>}
        />
        <GroupItem
          text="Мин. просмотры"
          after={<Text type="body">{formatNumber(request.min_views)}</Text>}
        />
      </Group>

      <Group header="Даты">
        <div className="px-4 py-3">
          <Text type="body" color="secondary">
            {formatMaybeJson(request.dates)}
          </Text>
        </div>
      </Group>

      {request.brief && (
        <Group header="Бриф">
          <div className="px-4 py-3">
            <Text type="body" color="secondary">
              {request.brief}
            </Text>
          </div>
        </Group>
      )}

      <div className="flex flex-col gap-2 pt-2">
        <Button text="Откликнуться" type="primary" onClick={respond} />
        <Button text="Назад" type="secondary" onClick={() => navigate(-1)} />
      </div>
    </div>
  );
}
