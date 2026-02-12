import { useCallback, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Button,
  Group,
  GroupItem,
  Input,
  Spinner,
  Text,
  useToast,
} from "@telegram-tools/ui-kit";
import { apiFetch, uploadMedia } from "../api/client";
import { useApi } from "../hooks/useApi";
import { useBackButton } from "../hooks/useBackButton";
import type { ListingDetail, MediaFileId } from "../types";
import { DateTimePickerField, localInputToIso } from "../components/DateTimePickerField";

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
  const [dealPrice, setDealPrice] = useState("");
  const [dealFormat, setDealFormat] = useState("post");
  const [publishAt, setPublishAt] = useState("");
  const [verificationWindow, setVerificationWindow] = useState("");
  const [brief, setBrief] = useState("");
  const [creativeExample, setCreativeExample] = useState("");
  const [creativeMedia, setCreativeMedia] = useState<MediaFileId[]>([]);
  const [mediaUploading, setMediaUploading] = useState(false);

  const listingId = Number(id);
  const fetcher = useCallback(() => apiFetch<ListingDetail>(`/listings/${listingId}`), [listingId]);
  const { data: listing, loading, error } = useApi(fetcher, [listingId]);

  const channel = listing?.channel ?? null;
  const stats = channel?.stats ?? null;

  const respond = async () => {
    if (!listing) return;
    try {
      const parsedPrice = dealPrice.trim() ? Number(dealPrice) : null;
      const parsedWindow = verificationWindow.trim() ? Number(verificationWindow) : null;
      const publishAtIso = localInputToIso(publishAt);
      if (publishAt.trim() && !publishAtIso) {
        showToast("Некорректная дата публикации", { type: "error" });
        return;
      }
      if ((dealPrice.trim() && Number.isNaN(parsedPrice)) || (verificationWindow.trim() && Number.isNaN(parsedWindow))) {
        showToast("Цена и окно верификации должны быть числом", { type: "error" });
        return;
      }
      const deal = await apiFetch<{ id: number }>("/deals", {
        method: "POST",
        body: JSON.stringify({
          listing_id: listing.id,
          channel_id: listing.channel_id,
          price: parsedPrice,
          format: dealFormat.trim() || listing.format,
          brief: brief.trim() || null,
          publish_at: publishAtIso,
          verification_window: parsedWindow,
        }),
      });
      const payloadTextParts = [];
      if (brief.trim()) payloadTextParts.push(`brief: ${brief.trim()}`);
      if (creativeExample.trim()) payloadTextParts.push(`creative_example: ${creativeExample.trim()}`);
      const media = creativeMedia.length > 0 ? creativeMedia : null;
      if (payloadTextParts.length > 0 || publishAtIso || media) {
        await apiFetch(`/deals/${deal.id}/advertiser_brief`, {
          method: "POST",
          body: JSON.stringify({
            text: payloadTextParts.join("\n"),
            publish_at: publishAtIso,
            media_file_ids: media,
          }),
        });
      }
      showToast("Сделка создана", { type: "success" });
      navigate(`/deals/${deal.id}`);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка", { type: "error" });
    }
  };

  const handleCreativeMediaFile = async (file: File | null) => {
    if (!file) return;
    setMediaUploading(true);
    try {
      const uploaded = await uploadMedia(file);
      setCreativeMedia((prev) => [...prev, { type: uploaded.type, file_id: uploaded.file_id }]);
      showToast("Файл загружен", { type: "success" });
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка загрузки", { type: "error" });
    } finally {
      setMediaUploading(false);
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

      <Group header="Отклик">
        <div className="flex flex-col gap-3 px-4 py-3">
          <Input
            placeholder="Ваша цена (опционально)"
            type="text"
            value={dealPrice}
            onChange={(v) => setDealPrice(v)}
            numeric
          />
          <Input
            placeholder="Формат"
            type="text"
            value={dealFormat}
            onChange={(v) => setDealFormat(v)}
          />
          <DateTimePickerField value={publishAt} onChange={setPublishAt} />
          <Input
            placeholder="verification_window (мин)"
            type="text"
            value={verificationWindow}
            onChange={(v) => setVerificationWindow(v)}
            numeric
          />
          <textarea
            className="w-full rounded-xl border border-[var(--tg-theme-hint-color,#ccc)] bg-transparent px-3 py-2 text-sm"
            rows={4}
            placeholder={"Бриф\nПример:\n- продукт\n- CTA\n- ограничения"}
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
          />
          <textarea
            className="w-full rounded-xl border border-[var(--tg-theme-hint-color,#ccc)] bg-transparent px-3 py-2 text-sm"
            rows={3}
            placeholder="Пример креатива текстом"
            value={creativeExample}
            onChange={(e) => setCreativeExample(e.target.value)}
          />
          <input
            type="file"
            accept="image/*,video/*,.gif,.pdf,.doc,.docx,.txt"
            onChange={(e) => handleCreativeMediaFile(e.target.files?.[0] ?? null)}
          />
          {creativeMedia.length > 0 && (
            <Text type="caption1" color="secondary">
              Файлы: {creativeMedia.map((item) => `${item.type}:${item.file_id.slice(0, 10)}...`).join(", ")}
            </Text>
          )}
          {mediaUploading && (
            <Text type="caption1" color="secondary">
              Загружаем файл...
            </Text>
          )}
        </div>
      </Group>

      <div className="flex flex-col gap-2 pt-2">
        <Button text="Откликнуться" type="primary" onClick={respond} />
        <Button text="Назад" type="secondary" onClick={() => navigate(-1)} />
      </div>
    </div>
  );
}
