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
import type { Deal, DealStatus } from "../types";

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

export function DealDetailPage() {
  useBackButton();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();

  const fetcher = useCallback(() => apiFetch<Deal>(`/deals/${id}`), [id]);
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

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <Text type="title2" weight="bold">
          Сделка #{deal.id}
        </Text>
        <DealStatusBadge status={deal.status as DealStatus} />
      </div>

      <Group header="Детали">
        <GroupItem text="Канал" after={<Text type="body">{`#${deal.channel_id}`}</Text>} />
        {deal.price != null && (
          <GroupItem text="Цена" after={<Text type="body">${deal.price}</Text>} />
        )}
        {deal.format && (
          <GroupItem text="Формат" after={<Text type="body">{deal.format}</Text>} />
        )}
        {deal.publish_at && (
          <GroupItem
            text="Публикация"
            after={
              <Text type="body">
                {new Date(deal.publish_at).toLocaleDateString("ru-RU")}
              </Text>
            }
          />
        )}
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
          onClick={() => {
            const tg = window.Telegram?.WebApp;
            if (tg) {
              tg.openTelegramLink(`${BOT_URL}?start=deal_${deal.id}`);
            }
          }}
        />
      </div>
    </div>
  );
}
