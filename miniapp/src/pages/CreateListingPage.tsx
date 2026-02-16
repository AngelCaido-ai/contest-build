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
  const [constraintLang, setConstraintLang] = useState<string | null>(null);
  const [constraintGeo, setConstraintGeo] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const langOptions = useMemo(
    () => [
      { value: "", label: "Language (not specified)" },
      { value: "en", label: "EN" },
      { value: "ru", label: "RU" },
      { value: "uk", label: "UK" },
      { value: "de", label: "DE" },
      { value: "fr", label: "FR" },
      { value: "es", label: "ES" },
      { value: "pt", label: "PT" },
      { value: "it", label: "IT" },
      { value: "ar", label: "AR" },
      { value: "zh", label: "ZH" },
      { value: "ja", label: "JA" },
      { value: "ko", label: "KO" },
      { value: "hi", label: "HI" },
      { value: "tr", label: "TR" },
      { value: "pl", label: "PL" },
    ],
    [],
  );

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
      showToast("Select a channel", { type: "error" });
      return;
    }
    let constraintsValue: Record<string, unknown> | null = null;
    const geoList = constraintGeo
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);
    if (constraintLang || geoList.length > 0) {
      constraintsValue = {};
      if (constraintLang) constraintsValue.lang = constraintLang;
      if (geoList.length > 0) constraintsValue.geo = geoList;
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
      showToast("Price must be a number", { type: "error" });
      return;
    }
    setSubmitting(true);
    try {
      await apiFetch("/listings", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      showToast("Listing created", { type: "success" });
      navigate("/listings");
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Error", { type: "error" });
    } finally {
      setSubmitting(false);
    }
  };

  if (!loading && ownerChannels.length === 0) {
    return (
      <div className="flex flex-col gap-4">
        <Text type="title2" weight="bold">
          Create Listing
        </Text>
        <Group>
          <div className="px-4 py-3">
            <Text type="body" color="secondary">
              First add a channel where you are the owner.
            </Text>
          </div>
        </Group>
        <Button text="Go to Channels" type="primary" onClick={() => navigate("/channels")} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Text type="title2" weight="bold">
        Create Listing
      </Text>

      <Group header="General">
        <div className="flex flex-col gap-3 px-4 py-3">
          <Select options={channelOptions} value={channelId} onChange={(v) => setChannelId(v)} />
          <Input
            placeholder="Price USD (optional)"
            type="text"
            value={priceUsd}
            onChange={(v) => setPriceUsd(v)}
            numeric
          />
          <Input
            placeholder="Price TON (optional)"
            type="text"
            value={priceTon}
            onChange={(v) => setPriceTon(v)}
            numeric
          />
          <Input
            placeholder="Format (e.g. post)"
            type="text"
            value={format}
            onChange={(v) => setFormat(v)}
          />
          <Input
            placeholder="Categories, comma-separated"
            type="text"
            value={categories}
            onChange={(v) => setCategories(v)}
          />
        </div>
      </Group>

      <Group header="Constraints">
        <div className="flex flex-col gap-3 px-4 py-3">
          <Select
            options={langOptions}
            value={constraintLang}
            onChange={(v) => setConstraintLang(v || null)}
          />
          <Input
            placeholder="Countries, comma-separated (e.g. US, UK, DE)"
            type="text"
            value={constraintGeo}
            onChange={(v) => setConstraintGeo(v)}
          />
        </div>
      </Group>

      <div className="flex flex-col gap-2">
        <Button text="Create" type="primary" loading={submitting} onClick={submit} />
        <Button text="Back" type="secondary" onClick={() => navigate(-1)} />
      </div>
    </div>
  );
}
