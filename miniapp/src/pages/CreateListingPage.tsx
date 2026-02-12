import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Group, Input, Select, Text, useToast } from "@telegram-tools/ui-kit";
import { apiFetch } from "../api/client";
import { useApi } from "../hooks/useApi";
import { useBackButton } from "../hooks/useBackButton";
import { useAuth } from "../contexts/AuthContext";
import type { Channel } from "../types";

export function CreateListingPage() {
  useBackButton();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { user } = useAuth();
  const [channelId, setChannelId] = useState<string | null>(null);
  const [priceUsd, setPriceUsd] = useState("");
  const [priceTon, setPriceTon] = useState("");
  const [format, setFormat] = useState("post");
  const [categories, setCategories] = useState("");
  const [constraints, setConstraints] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fetchChannels = useCallback(() => apiFetch<Channel[]>("/channels"), []);
  const { data: channels, loading } = useApi(fetchChannels, []);

  const ownerChannels = useMemo(
    () => (channels ?? []).filter((ch) => ch.owner_user_id === user?.id),
    [channels, user?.id],
  );
  const channelOptions = useMemo(
    () =>
      ownerChannels.map((ch) => ({
        value: String(ch.id),
        label: ch.title ?? (ch.username ? `@${ch.username}` : `#${ch.tg_chat_id}`),
      })),
    [ownerChannels],
  );

  useEffect(() => {
    if (!channelId && ownerChannels.length > 0) {
      setChannelId(String(ownerChannels[0].id));
    }
  }, [channelId, ownerChannels]);

  const submit = async () => {
    if (!channelId) {
      showToast("Выберите канал", { type: "error" });
      return;
    }
    let constraintsValue: Record<string, unknown> | null = null;
    if (constraints.trim()) {
      try {
        constraintsValue = JSON.parse(constraints);
      } catch {
        showToast("Поле constraints должно быть JSON", { type: "error" });
        return;
      }
    }
    const payload = {
      channel_id: Number(channelId),
      price_usd: priceUsd.trim() ? Number(priceUsd) : null,
      price_ton: priceTon.trim() ? Number(priceTon) : null,
      format: format.trim() || "post",
      categories: categories
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
      constraints: constraintsValue,
      active: true,
    };
    if (
      (priceUsd.trim() && Number.isNaN(payload.price_usd as number)) ||
      (priceTon.trim() && Number.isNaN(payload.price_ton as number))
    ) {
      showToast("Цена должна быть числом", { type: "error" });
      return;
    }
    setSubmitting(true);
    try {
      await apiFetch("/listings", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      showToast("Листинг создан", { type: "success" });
      navigate("/listings");
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка", { type: "error" });
    } finally {
      setSubmitting(false);
    }
  };

  if (!loading && ownerChannels.length === 0) {
    return (
      <div className="flex flex-col gap-4">
        <Text type="title2" weight="bold">
          Создать листинг
        </Text>
        <Group>
          <div className="px-4 py-3">
            <Text type="body" color="secondary">
              Сначала добавьте канал, где вы владелец.
            </Text>
          </div>
        </Group>
        <Button text="К каналам" type="primary" onClick={() => navigate("/channels")} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Text type="title2" weight="bold">
        Создать листинг
      </Text>

      <Group header="Основное">
        <div className="flex flex-col gap-3 px-4 py-3">
          <Select options={channelOptions} value={channelId} onChange={(v) => setChannelId(v)} />
          <Input
            placeholder="Цена USD (опционально)"
            type="text"
            value={priceUsd}
            onChange={(v) => setPriceUsd(v)}
            numeric
          />
          <Input
            placeholder="Цена TON (опционально)"
            type="text"
            value={priceTon}
            onChange={(v) => setPriceTon(v)}
            numeric
          />
          <Input
            placeholder="Формат (например post)"
            type="text"
            value={format}
            onChange={(v) => setFormat(v)}
          />
          <Input
            placeholder="Категории через запятую"
            type="text"
            value={categories}
            onChange={(v) => setCategories(v)}
          />
          <textarea
            className="w-full rounded-xl border border-[var(--tg-theme-hint-color,#ccc)] bg-transparent px-3 py-2 text-sm"
            rows={4}
            placeholder='constraints JSON, например {"lang":"ru"}'
            value={constraints}
            onChange={(e) => setConstraints(e.target.value)}
          />
        </div>
      </Group>

      <div className="flex flex-col gap-2">
        <Button text="Создать" type="primary" loading={submitting} onClick={submit} />
        <Button text="Назад" type="secondary" onClick={() => navigate(-1)} />
      </div>
    </div>
  );
}
