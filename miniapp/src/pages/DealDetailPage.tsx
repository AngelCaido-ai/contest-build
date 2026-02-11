import { useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Text,
  Button,
  Group,
  GroupItem,
  Spinner,
  useToast,
} from "@telegram-tools/ui-kit";
import { apiFetch } from "../api/client";
import { useApi } from "../hooks/useApi";
import { useBackButton } from "../hooks/useBackButton";
import { DealStatusBadge } from "../components/DealStatusBadge";
import type { DealDetail, DealEvent, DealStatus } from "../types";

const BOT_URL = import.meta.env.VITE_BOT_URL || "https://t.me/build_contest_ads_bot";

function getCta(status: DealStatus): { label: string; action: "pay" | "bot" | null } {
  switch (status) {
    case "NEGOTIATING":
    case "TERMS_LOCKED":
      return { label: "Перейти к оплате", action: "pay" };
    case "AWAITING_PAYMENT":
      return { label: "Оплатить", action: "pay" };
    case "FUNDED":
    case "CREATIVE_DRAFT":
    case "CREATIVE_REVIEW":
    case "APPROVED":
    case "SCHEDULED":
      return { label: "Перейти в бота", action: "bot" };
    case "POSTED":
    case "VERIFYING":
      return { label: "Проверить в боте", action: "bot" };
    default:
      return { label: "", action: null };
  }
}

function formatDate(value: string | null | undefined) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("ru-RU");
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("ru-RU");
}

function formatInt(value: number | null | undefined) {
  if (value == null) return "—";
  return value.toLocaleString("ru-RU");
}

function formatPayload(payload: DealEvent["payload"]) {
  if (!payload) return null;
  try {
    const text = JSON.stringify(payload);
    if (text.length <= 160) return text;
    return text.slice(0, 160) + "…";
  } catch {
    return null;
  }
}

export function DealDetailPage() {
  useBackButton();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();

  const fetcher = useCallback(() => apiFetch<DealDetail>(`/deals/${id}`), [id]);
  const { data: deal, loading, error } = useApi(fetcher, [id]);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner size="32px" />
      </div>
    );
  }

  if (error || !deal) {
    return (
      <div className="flex flex-col items-center gap-3 py-12">
        <Text type="body" color="danger">{error ?? "Сделка не найдена"}</Text>
        <Button text="Назад" type="secondary" onClick={() => navigate(-1)} />
      </div>
    );
  }

  const cta = getCta(deal.status as DealStatus);

  const channelTitle =
    deal.channel_info?.title ||
    (deal.channel_info?.username ? `@${deal.channel_info.username}` : null) ||
    `#${deal.channel_id}`;
  const channelUsername = deal.channel_info?.username
    ? deal.channel_info.username.replace(/^@/, "")
    : null;

  const handleCta = () => {
    if (cta.action === "pay") {
      navigate(`/deals/${deal.id}/pay`);
    } else if (cta.action === "bot") {
      const tg = window.Telegram?.WebApp;
      if (tg) {
        tg.openTelegramLink(`${BOT_URL}?start=deal_${deal.id}`);
      } else {
        showToast("Telegram WebApp недоступен", { type: "error" });
      }
    }
  };

  const handleOpenBot = () => {
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.openTelegramLink(`${BOT_URL}?start=deal_${deal.id}`);
    } else {
      showToast("Telegram WebApp недоступен", { type: "error" });
    }
  };

  const handleOpenChannel = () => {
    if (!channelUsername) return;
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.openTelegramLink(`https://t.me/${channelUsername}`);
    } else {
      showToast("Telegram WebApp недоступен", { type: "error" });
    }
  };

  const events = deal.events ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <Text type="title2" weight="bold">
          Сделка #{deal.id}
        </Text>
        <DealStatusBadge status={deal.status as DealStatus} />
      </div>

      <Group header="Канал">
        <GroupItem
          text="Канал"
          after={<Text type="body">{channelTitle}</Text>}
          description={
            <div className="flex flex-col gap-0.5">
              {channelUsername && (
                <Text type="caption1" color="secondary">
                  @{channelUsername}
                </Text>
              )}
              <Text type="caption1" color="secondary">
                Подписчики: {formatInt(deal.channel_info?.subscribers)} · Просмотры/пост:{" "}
                {formatInt(deal.channel_info?.views_per_post)}
              </Text>
            </div>
          }
          onClick={channelUsername ? handleOpenChannel : undefined}
          chevron={Boolean(channelUsername)}
        />
      </Group>

      <Group header="Детали">
        <GroupItem text="ID сделки" after={<Text type="body">{deal.id}</Text>} />
        {deal.price != null && (
          <GroupItem text="Цена" after={<Text type="body">${deal.price}</Text>} />
        )}
        <GroupItem
          text="Формат"
          after={<Text type="body">{deal.format ?? "—"}</Text>}
        />
        <GroupItem
          text="Рекламодатель"
          after={
            <Text type="body">
              {deal.advertiser_info?.tg_username
                ? `@${deal.advertiser_info.tg_username.replace(/^@/, "")}`
                : "—"}
            </Text>
          }
        />
        <GroupItem
          text="Листинг"
          after={<Text type="body">{deal.listing_id ?? "—"}</Text>}
        />
        <GroupItem
          text="Заявка"
          after={<Text type="body">{deal.request_id ?? "—"}</Text>}
        />
        <GroupItem text="Создана" after={<Text type="body">{formatDateTime(deal.created_at)}</Text>} />
        <GroupItem text="Обновлена" after={<Text type="body">{formatDateTime(deal.updated_at)}</Text>} />
      </Group>

      <Group header="Публикация и проверка">
        <GroupItem text="Публикация (план)" after={<Text type="body">{formatDate(deal.publish_at)}</Text>} />
        <GroupItem text="Публикация (факт)" after={<Text type="body">{formatDateTime(deal.posted_at)}</Text>} />
        <GroupItem
          text="ID сообщения"
          after={<Text type="body">{deal.posted_message_id ?? "—"}</Text>}
        />
        <GroupItem
          text="Окно верификации"
          after={
            <Text type="body">
              {deal.verification_window != null ? `${deal.verification_window} мин` : "—"}
            </Text>
          }
        />
        <GroupItem
          text="Проверка началась"
          after={<Text type="body">{formatDateTime(deal.verification_started_at)}</Text>}
        />
      </Group>

      {deal.brief && (
        <Group header="Бриф">
          <div className="px-4 py-3">
            <Text type="body" color="secondary">
              {deal.brief}
            </Text>
          </div>
        </Group>
      )}

      <Group header="История">
        {events.length === 0 ? (
          <div className="px-4 py-3">
            <Text type="body" color="secondary">
              Нет событий
            </Text>
          </div>
        ) : (
          events.map((ev) => (
            <GroupItem
              key={ev.id}
              text={ev.type}
              description={
                <div className="flex flex-col gap-0.5">
                  <Text type="caption1" color="secondary">
                    {formatDateTime(ev.created_at)}
                  </Text>
                  {formatPayload(ev.payload) && (
                    <Text type="caption1" color="secondary">
                      {formatPayload(ev.payload)}
                    </Text>
                  )}
                </div>
              }
            />
          ))
        )}
      </Group>

      {deal.tampered && (
        <Group>
          <div className="px-4 py-3">
            <Text type="body" color="danger">
              Пост был изменен после публикации
            </Text>
          </div>
        </Group>
      )}

      {deal.deleted && (
        <Group>
          <div className="px-4 py-3">
            <Text type="body" color="danger">
              Пост был удален
            </Text>
          </div>
        </Group>
      )}

      <div className="flex flex-col gap-2 pt-2">
        {cta.action && (
          <Button text={cta.label} type="primary" onClick={handleCta} />
        )}
        <Button
          text="Перейти в бота"
          type="secondary"
          onClick={handleOpenBot}
        />
      </div>
    </div>
  );
}
