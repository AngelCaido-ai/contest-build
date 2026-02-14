import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Button,
  Group,
  GroupItem,
  Input,
  Select,
  Spinner,
  Text,
  useToast,
} from "@telegram-tools/ui-kit";
import { apiFetch } from "../api/client";
import { useApi } from "../hooks/useApi";
import { useBackButton } from "../hooks/useBackButton";
import type { Channel, RequestItem } from "../types";
import { DateTimePickerField, localInputToIso } from "../components/DateTimePickerField";

function formatNumber(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US").format(value);
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
  const [dealPrice, setDealPrice] = useState("");
  const [dealFormat, setDealFormat] = useState("post");
  const [publishAt, setPublishAt] = useState("");
  const [verificationWindow, setVerificationWindow] = useState("");
  const [brief, setBrief] = useState("");

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

  useEffect(() => {
    if (!request) return;
    if (request.budget != null) setDealPrice(String(request.budget));
  }, [request]);

  const refreshStats = async () => {
    if (!selectedChannel) return;
    try {
      await apiFetch(`/stats/channels/${selectedChannel.id}/refresh`, { method: "POST" });
      showToast("Stats updated", { type: "success" });
      refetchChannels();
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Error", { type: "error" });
    }
  };

  const respond = async () => {
    if (!request || !selectedChannel) {
      showToast("Select a channel", { type: "error" });
      return;
    }
    try {
      const parsedPrice = dealPrice.trim() ? Number(dealPrice) : null;
      const parsedWindow = verificationWindow.trim() ? Number(verificationWindow) : null;
      const publishAtIso = localInputToIso(publishAt);
      if (publishAt.trim() && !publishAtIso) {
        showToast("Invalid publish date", { type: "error" });
        return;
      }
      if ((dealPrice.trim() && Number.isNaN(parsedPrice)) || (verificationWindow.trim() && Number.isNaN(parsedWindow))) {
        showToast("Price and verification window must be numbers", { type: "error" });
        return;
      }
      const deal = await apiFetch<{ id: number }>("/deals", {
        method: "POST",
        body: JSON.stringify({
          request_id: request.id,
          channel_id: selectedChannel.id,
          price: parsedPrice ?? request.budget ?? null,
          format: dealFormat.trim() || "post",
          brief: brief.trim() || request.brief || null,
          publish_at: publishAtIso,
          verification_window: parsedWindow,
        }),
      });
      showToast("Deal created", { type: "success" });
      navigate(`/deals/${deal.id}`);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Error", { type: "error" });
    }
  };

  if (!id || Number.isNaN(requestId)) {
    return (
      <div className="flex flex-col items-center gap-3 py-12">
        <Text type="body" color="danger">Invalid request</Text>
        <Button text="Back" type="secondary" onClick={() => navigate(-1)} />
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
        <Text type="body" color="danger">{requestError ?? "Request not found"}</Text>
        <Button text="Back" type="secondary" onClick={() => navigate(-1)} />
      </div>
    );
  }

  if (channelsError || !channels || channels.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 py-12">
        <Text type="body" color="danger">
          {channelsError ?? "Add a channel first"}
        </Text>
        <Button text="Back" type="secondary" onClick={() => navigate(-1)} />
      </div>
    );
  }

  const stats = selectedChannel?.stats ?? null;

  return (
    <div className="flex flex-col gap-4">
      <Text type="title2" weight="bold">
        Preview
      </Text>

      <Group header="Channel">
        <div className="px-4 py-2">
          <Select
            options={channelOptions}
            value={selectedChannelId ?? String((selectedChannel ?? channels[0]).id)}
            onChange={(v) => setSelectedChannelId(v)}
          />
        </div>
        <GroupItem
          text="Stats"
          description={
            stats
              ? `${formatNumber(stats.subscribers)} subscribers · ${formatNumber(stats.views_per_post)} views`
              : "Stats not loaded"
          }
          after={<Button text="Refresh" type="secondary" onClick={refreshStats} />}
        />
      </Group>

      <Group header="Request Terms">
        <GroupItem
          text="Budget"
          after={<Text type="body">{request.budget != null ? `$${request.budget}` : "—"}</Text>}
        />
        <GroupItem
          text="Niche"
          after={<Text type="body">{request.niche ?? "—"}</Text>}
        />
        <GroupItem
          text="Languages"
          after={<Text type="body">{request.languages?.length ? request.languages.join(", ") : "—"}</Text>}
        />
        <GroupItem
          text="Min. subscribers"
          after={<Text type="body">{formatNumber(request.min_subs)}</Text>}
        />
        <GroupItem
          text="Min. views"
          after={<Text type="body">{formatNumber(request.min_views)}</Text>}
        />
      </Group>

      <Group header="Dates">
        <div className="px-4 py-3">
          <Text type="body" color="secondary">
            {formatMaybeJson(request.dates)}
          </Text>
        </div>
      </Group>

      {request.brief && (
        <Group header="Brief">
          <div className="px-4 py-3">
            <Text type="body" color="secondary">
              {request.brief}
            </Text>
          </div>
        </Group>
      )}

      <Group header="Response Parameters">
        <div className="flex flex-col gap-3 px-4 py-3">
          <Input
            placeholder="Your price (optional)"
            type="text"
            value={dealPrice}
            onChange={(v) => setDealPrice(v)}
            numeric
          />
          <Input
            placeholder="Format"
            type="text"
            value={dealFormat}
            onChange={(v) => setDealFormat(v)}
          />
          <DateTimePickerField value={publishAt} onChange={setPublishAt} />
          <Input
            placeholder="verification_window (min)"
            type="text"
            value={verificationWindow}
            onChange={(v) => setVerificationWindow(v)}
            numeric
          />
          <textarea
            className="w-full rounded-xl border border-[var(--tg-theme-hint-color,#ccc)] bg-transparent px-3 py-2 text-sm"
            rows={4}
            placeholder="Comment/deal terms"
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
          />
        </div>
      </Group>

      <div className="flex flex-col gap-2 pt-2">
        <Button text="Respond" type="primary" onClick={respond} />
        <Button text="Back" type="secondary" onClick={() => navigate(-1)} />
      </div>
    </div>
  );
}
