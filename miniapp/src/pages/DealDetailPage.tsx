import { useCallback, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Text,
  Button,
  Group,
  GroupItem,
  Spinner,
  Input,
  Select,
  useToast,
} from "@telegram-tools/ui-kit";
import { apiFetch, uploadMedia } from "../api/client";
import { useApi } from "../hooks/useApi";
import { useBackButton } from "../hooks/useBackButton";
import { DealStatusBadge } from "../components/DealStatusBadge";
import type { DealDetail, DealEvent, DealStatus, MediaFileId } from "../types";
import { useAuth } from "../contexts/AuthContext";
import { DateTimePickerField, localInputToIso } from "../components/DateTimePickerField";

const BOT_URL = import.meta.env.VITE_BOT_URL || "https://t.me/build_contest_ads_bot";
const CREATIVE_VIEW_STATUSES = new Set<DealStatus>([
  "CREATIVE_REVIEW",
  "CREATIVE_DRAFT",
  "APPROVED",
  "SCHEDULED",
  "POSTED",
  "VERIFYING",
  "RELEASED",
]);
const STATUS_TRANSITIONS: Record<DealStatus, DealStatus[]> = {
  NEGOTIATING: ["TERMS_LOCKED", "CANCELED"],
  TERMS_LOCKED: ["AWAITING_PAYMENT", "CREATIVE_DRAFT", "CANCELED"],
  AWAITING_PAYMENT: ["FUNDED", "CANCELED"],
  FUNDED: ["CREATIVE_DRAFT", "CANCELED"],
  CREATIVE_DRAFT: ["CREATIVE_REVIEW", "CANCELED"],
  CREATIVE_REVIEW: ["APPROVED", "CANCELED"],
  APPROVED: ["SCHEDULED", "CANCELED"],
  SCHEDULED: ["POSTED", "CANCELED"],
  POSTED: ["VERIFYING"],
  VERIFYING: ["RELEASED", "REFUNDED"],
  RELEASED: [],
  REFUNDED: [],
  CANCELED: [],
};
const ROLE_ALLOWED_STATUSES: Record<"owner" | "advertiser", DealStatus[]> = {
  owner: ["TERMS_LOCKED", "CANCELED", "SCHEDULED", "POSTED", "VERIFYING", "RELEASED", "REFUNDED"],
  advertiser: ["AWAITING_PAYMENT", "FUNDED", "CANCELED"],
};

type CreativePayload = {
  id: number;
  version: number;
  text: string | null;
  media_file_ids: Array<MediaFileId | string> | null;
  status: string;
};

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
  const { user } = useAuth();
  const [termsPrice, setTermsPrice] = useState("");
  const [termsFormat, setTermsFormat] = useState("");
  const [termsPublishAt, setTermsPublishAt] = useState("");
  const [termsWindow, setTermsWindow] = useState("");
  const [publishAtValue, setPublishAtValue] = useState("");
  const [statusValue, setStatusValue] = useState<string | null>(null);
  const [creativeText, setCreativeText] = useState("");
  const [creativeMedia, setCreativeMedia] = useState<MediaFileId[]>([]);
  const [creativeUploading, setCreativeUploading] = useState(false);
  const [creativeStatus, setCreativeStatus] = useState<string | null>("APPROVED");
  const [creativeComment, setCreativeComment] = useState("");
  const [creativePublishAt, setCreativePublishAt] = useState("");
  const [briefText, setBriefText] = useState("");
  const [briefPublishAt, setBriefPublishAt] = useState("");
  const [briefMedia, setBriefMedia] = useState<MediaFileId[]>([]);
  const [briefUploading, setBriefUploading] = useState(false);
  const [creativeData, setCreativeData] = useState<CreativePayload | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [wizardStep, setWizardStep] = useState(0);
  const [showAllActions, setShowAllActions] = useState(false);

  const fetcher = useCallback(() => apiFetch<DealDetail>(`/deals/${id}`), [id]);
  const { data: deal, loading, error, refetch } = useApi(fetcher, [id]);

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
  const isAdvertiser = user?.id === deal.advertiser_id;
  const role: "owner" | "advertiser" = isAdvertiser ? "advertiser" : "owner";
  const status = deal.status as DealStatus;
  const allowedStatuses = (STATUS_TRANSITIONS[status] ?? []).filter((item) =>
    ROLE_ALLOWED_STATUSES[role].includes(item),
  );
  const canEditTerms = role === "owner" && (status === "NEGOTIATING" || status === "TERMS_LOCKED");
  const canSetPublishAt =
    role === "owner" &&
    !["NEGOTIATING", "TERMS_LOCKED", "POSTED", "VERIFYING", "RELEASED", "REFUNDED", "CANCELED"].includes(status);
  const canCreateCreative = role === "owner" && (status === "FUNDED" || status === "CREATIVE_DRAFT");
  const canReviewCreative = role === "advertiser" && status === "CREATIVE_REVIEW";
  const canSendBrief = role === "advertiser" && !["RELEASED", "REFUNDED", "CANCELED"].includes(status);
  const canViewCreative = CREATIVE_VIEW_STATUSES.has(status);
  const wizardSteps = [
    ...(canEditTerms ? [{ key: "terms", title: "Условия" }] : []),
    ...(canSetPublishAt || allowedStatuses.length > 0 ? [{ key: "workflow", title: "Дата и статус" }] : []),
    ...(canCreateCreative ? [{ key: "creative", title: "Креатив" }] : []),
    ...(canReviewCreative ? [{ key: "review", title: "Ревью" }] : []),
    ...(canSendBrief ? [{ key: "brief", title: "Бриф" }] : []),
    ...(canViewCreative ? [{ key: "view", title: "Просмотр" }] : []),
  ];
  const safeWizardStep = wizardSteps.length > 0 ? Math.min(wizardStep, wizardSteps.length - 1) : 0;
  const activeWizardStep = wizardSteps[safeWizardStep]?.key ?? null;
  const isStepVisible = (key: string) => showAllActions || wizardSteps.length === 0 || activeWizardStep === key;
  const statusOptions = allowedStatuses.map((item) => ({ value: item, label: item }));
  const creativeStatusOptions = [
    { value: "APPROVED", label: "APPROVED" },
    { value: "DRAFT", label: "DRAFT" },
  ];

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

  const withSubmitting = async (action: () => Promise<void>) => {
    setSubmitting(true);
    try {
      await action();
      await refetch();
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка", { type: "error" });
    } finally {
      setSubmitting(false);
    }
  };

  const submitTerms = async () => {
    await withSubmitting(async () => {
      const payload: Record<string, unknown> = {};
      if (termsPrice.trim()) payload.price = Number(termsPrice);
      if (termsFormat.trim()) payload.format = termsFormat.trim();
      if (termsPublishAt.trim()) {
        const publishAtIso = localInputToIso(termsPublishAt);
        if (!publishAtIso) {
          throw new Error("Некорректная дата публикации");
        }
        payload.publish_at = publishAtIso;
      }
      if (termsWindow.trim()) payload.verification_window = Number(termsWindow);
      if (
        (payload.price !== undefined && Number.isNaN(payload.price as number)) ||
        (payload.verification_window !== undefined && Number.isNaN(payload.verification_window as number))
      ) {
        throw new Error("Цена и окно верификации должны быть числом");
      }
      if (Object.keys(payload).length === 0) {
        throw new Error("Заполните хотя бы одно поле");
      }
      await apiFetch(`/deals/${deal.id}/terms`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      showToast("Условия обновлены", { type: "success" });
    });
  };

  const submitPublishAt = async () => {
    await withSubmitting(async () => {
      const publishAtIso = localInputToIso(publishAtValue);
      if (!publishAtIso) {
        throw new Error("Укажите publish_at");
      }
      await apiFetch(`/deals/${deal.id}/publish_at`, {
        method: "POST",
        body: JSON.stringify({ publish_at: publishAtIso }),
      });
      showToast("Дата публикации обновлена", { type: "success" });
    });
  };

  const submitStatus = async () => {
    await withSubmitting(async () => {
      const selectedStatus = statusValue ?? allowedStatuses[0];
      if (!selectedStatus) {
        throw new Error("Выберите статус");
      }
      await apiFetch(`/deals/${deal.id}/status`, {
        method: "POST",
        body: JSON.stringify({ status: selectedStatus }),
      });
      showToast("Статус обновлен", { type: "success" });
    });
  };

  const submitCreative = async () => {
    await withSubmitting(async () => {
      if (!creativeText.trim() && creativeMedia.length === 0) {
        throw new Error("Добавьте текст или медиа");
      }
      await apiFetch(`/deals/${deal.id}/creative`, {
        method: "POST",
        body: JSON.stringify({
          text: creativeText.trim() || null,
          media_file_ids: creativeMedia.length > 0 ? creativeMedia : null,
        }),
      });
      showToast("Креатив отправлен", { type: "success" });
      setCreativeText("");
      setCreativeMedia([]);
    });
  };

  const submitCreativeReview = async () => {
    await withSubmitting(async () => {
      if (!creativeStatus) {
        throw new Error("Выберите статус креатива");
      }
      const publishAtIso = localInputToIso(creativePublishAt);
      if (creativePublishAt.trim() && !publishAtIso) {
        throw new Error("Некорректная дата публикации");
      }
      await apiFetch(`/deals/${deal.id}/creative/status`, {
        method: "POST",
        body: JSON.stringify({
          status: creativeStatus,
          comment: creativeComment.trim() || null,
          publish_at: publishAtIso,
        }),
      });
      showToast("Ревью отправлено", { type: "success" });
      setCreativeComment("");
    });
  };

  const submitBrief = async () => {
    await withSubmitting(async () => {
      const publishAtIso = localInputToIso(briefPublishAt);
      if (briefPublishAt.trim() && !publishAtIso) {
        throw new Error("Некорректная дата публикации");
      }
      if (!briefText.trim() && !publishAtIso && briefMedia.length === 0) {
        throw new Error("Заполните бриф или дату публикации");
      }
      await apiFetch(`/deals/${deal.id}/advertiser_brief`, {
        method: "POST",
        body: JSON.stringify({
          text: briefText.trim() || null,
          publish_at: publishAtIso,
          media_file_ids: briefMedia.length > 0 ? briefMedia : null,
        }),
      });
      showToast("Бриф отправлен", { type: "success" });
      setBriefText("");
      setBriefMedia([]);
    });
  };

  const handleCreativeFile = async (file: File | null) => {
    if (!file) return;
    setCreativeUploading(true);
    try {
      const uploaded = await uploadMedia(file);
      setCreativeMedia((prev) => [...prev, { type: uploaded.type, file_id: uploaded.file_id }]);
      showToast("Медиа добавлено", { type: "success" });
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка загрузки", { type: "error" });
    } finally {
      setCreativeUploading(false);
    }
  };

  const handleBriefFile = async (file: File | null) => {
    if (!file) return;
    setBriefUploading(true);
    try {
      const uploaded = await uploadMedia(file);
      setBriefMedia((prev) => [...prev, { type: uploaded.type, file_id: uploaded.file_id }]);
      showToast("Медиа добавлено", { type: "success" });
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка загрузки", { type: "error" });
    } finally {
      setBriefUploading(false);
    }
  };

  const loadCreative = async () => {
    await withSubmitting(async () => {
      const result = await apiFetch<CreativePayload>(`/deals/${deal.id}/creative`);
      setCreativeData(result);
    });
  };

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

      {(canEditTerms || canSetPublishAt || allowedStatuses.length > 0 || canCreateCreative || canReviewCreative || canSendBrief || canViewCreative) && (
        <Text type="title3" weight="bold">
          Действия
        </Text>
      )}

      {wizardSteps.length > 0 && (
        <Group header="Пошаговый сценарий">
          <div className="flex flex-col gap-3 px-4 py-3">
            <Text type="body">
              Шаг {safeWizardStep + 1} из {wizardSteps.length}: {wizardSteps[safeWizardStep]?.title}
            </Text>
            <Text type="caption1" color="secondary">
              {wizardSteps.map((step, index) => `${index + 1}. ${step.title}`).join("  |  ")}
            </Text>
            <div className="flex gap-2">
              <Button
                text="Назад"
                type="secondary"
                disabled={safeWizardStep <= 0}
                onClick={() => setWizardStep((prev) => Math.max(prev - 1, 0))}
              />
              <Button
                text="Далее"
                type="secondary"
                disabled={safeWizardStep >= wizardSteps.length - 1}
                onClick={() => setWizardStep((prev) => Math.min(prev + 1, wizardSteps.length - 1))}
              />
            </div>
            <Button
              text={showAllActions ? "Показывать по шагам" : "Показать все блоки"}
              type="secondary"
              onClick={() => setShowAllActions((prev) => !prev)}
            />
          </div>
        </Group>
      )}

      {canEditTerms && isStepVisible("terms") && (
        <Group header="Условия сделки">
          <div className="flex flex-col gap-3 px-4 py-3">
            <Input
              placeholder="Цена"
              type="text"
              value={termsPrice}
              onChange={(v) => setTermsPrice(v)}
              numeric
            />
            <Input
              placeholder="Формат"
              type="text"
              value={termsFormat}
              onChange={(v) => setTermsFormat(v)}
            />
            <DateTimePickerField value={termsPublishAt} onChange={setTermsPublishAt} />
            <Input
              placeholder="verification_window (мин)"
              type="text"
              value={termsWindow}
              onChange={(v) => setTermsWindow(v)}
              numeric
            />
            <Button text="Зафиксировать условия" type="primary" loading={submitting} onClick={submitTerms} />
          </div>
        </Group>
      )}

      {canSetPublishAt && isStepVisible("workflow") && (
        <Group header="Дата публикации">
          <div className="flex flex-col gap-3 px-4 py-3">
            <DateTimePickerField value={publishAtValue} onChange={setPublishAtValue} allowEmpty={false} />
            <Button text="Обновить дату" type="secondary" loading={submitting} onClick={submitPublishAt} />
          </div>
        </Group>
      )}

      {allowedStatuses.length > 0 && isStepVisible("workflow") && (
        <Group header="Смена статуса">
          <div className="flex flex-col gap-3 px-4 py-3">
            <Select
              options={statusOptions}
              value={statusValue ?? (statusOptions.length > 0 ? statusOptions[0].value : null)}
              onChange={(v) => setStatusValue(v)}
            />
            <Button text="Обновить статус" type="secondary" loading={submitting} onClick={submitStatus} />
          </div>
        </Group>
      )}

      {canCreateCreative && isStepVisible("creative") && (
        <Group header="Креатив">
          <div className="flex flex-col gap-3 px-4 py-3">
            <textarea
              className="w-full rounded-xl border border-[var(--tg-theme-hint-color,#ccc)] bg-transparent px-3 py-2 text-sm"
              rows={4}
              placeholder="Текст креатива"
              value={creativeText}
              onChange={(e) => setCreativeText(e.target.value)}
            />
            <input
              type="file"
              accept="image/*,video/*,.gif,.pdf,.doc,.docx,.txt"
              onChange={(e) => handleCreativeFile(e.target.files?.[0] ?? null)}
            />
            {creativeMedia.length > 0 && (
              <Text type="caption1" color="secondary">
                Файлы: {creativeMedia.map((item) => `${item.type}:${item.file_id.slice(0, 10)}...`).join(", ")}
              </Text>
            )}
            {creativeUploading && (
              <Text type="caption1" color="secondary">
                Загружаем файл...
              </Text>
            )}
            <Button text="Отправить креатив" type="primary" loading={submitting} onClick={submitCreative} />
          </div>
        </Group>
      )}

      {canReviewCreative && isStepVisible("review") && (
        <Group header="Ревью креатива">
          <div className="flex flex-col gap-3 px-4 py-3">
            <Select options={creativeStatusOptions} value={creativeStatus} onChange={(v) => setCreativeStatus(v)} />
            <textarea
              className="w-full rounded-xl border border-[var(--tg-theme-hint-color,#ccc)] bg-transparent px-3 py-2 text-sm"
              rows={3}
              placeholder="Комментарий для DRAFT"
              value={creativeComment}
              onChange={(e) => setCreativeComment(e.target.value)}
            />
            <DateTimePickerField value={creativePublishAt} onChange={setCreativePublishAt} />
            <Button text="Отправить ревью" type="primary" loading={submitting} onClick={submitCreativeReview} />
          </div>
        </Group>
      )}

      {canSendBrief && isStepVisible("brief") && (
        <Group header="Бриф рекламодателя">
          <div className="flex flex-col gap-3 px-4 py-3">
            <textarea
              className="w-full rounded-xl border border-[var(--tg-theme-hint-color,#ccc)] bg-transparent px-3 py-2 text-sm"
              rows={4}
              placeholder="Что нужно в посте, CTA, ограничения"
              value={briefText}
              onChange={(e) => setBriefText(e.target.value)}
            />
            <DateTimePickerField value={briefPublishAt} onChange={setBriefPublishAt} />
            <input
              type="file"
              accept="image/*,video/*,.gif,.pdf,.doc,.docx,.txt"
              onChange={(e) => handleBriefFile(e.target.files?.[0] ?? null)}
            />
            {briefMedia.length > 0 && (
              <Text type="caption1" color="secondary">
                Файлы: {briefMedia.map((item) => `${item.type}:${item.file_id.slice(0, 10)}...`).join(", ")}
              </Text>
            )}
            {briefUploading && (
              <Text type="caption1" color="secondary">
                Загружаем файл...
              </Text>
            )}
            <Button text="Отправить бриф" type="secondary" loading={submitting} onClick={submitBrief} />
          </div>
        </Group>
      )}

      {canViewCreative && isStepVisible("view") && (
        <Group header="Просмотр креатива">
          <div className="flex flex-col gap-3 px-4 py-3">
            <Button text="Показать последний креатив" type="secondary" loading={submitting} onClick={loadCreative} />
            {creativeData && (
              <div className="flex flex-col gap-2 rounded-xl border border-[var(--tg-theme-hint-color,#ccc)] p-3">
                <Text type="body">Версия: {creativeData.version}</Text>
                <Text type="body">Статус: {creativeData.status}</Text>
                <Text type="body" color="secondary">
                  {creativeData.text || "Без текста"}
                </Text>
                <Text type="caption1" color="secondary">
                  media_file_ids: {JSON.stringify(creativeData.media_file_ids ?? [])}
                </Text>
              </div>
            )}
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
