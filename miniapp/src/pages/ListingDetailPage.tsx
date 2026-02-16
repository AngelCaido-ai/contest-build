import { useCallback, useEffect, useState } from "react";
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
import { ApiError, apiFetch, uploadMedia } from "../api/client";
import { useApi } from "../hooks/useApi";
import { useBackButton } from "../hooks/useBackButton";
import type { ListingDetail, MediaFileId } from "../types";
import { DateTimePickerField, localInputToIso } from "../components/DateTimePickerField";

function formatNumber(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US").format(value);
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

  useEffect(() => {
    if (!listing) return;
    if (listing.price_usd != null) setDealPrice(String(listing.price_usd));
    if (listing.format) setDealFormat(listing.format);
  }, [listing]);

  const respond = async () => {
    if (!listing) return;
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
          listing_id: listing.id,
          channel_id: listing.channel_id,
          price: parsedPrice ?? listing.price_usd ?? null,
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
      showToast("Deal created", { type: "success" });
      navigate(`/deals/${deal.id}`);
    } catch (e) {
      if (
        e instanceof ApiError &&
        e.status === 409 &&
        e.detail &&
        typeof e.detail === "object" &&
        "deal_id" in e.detail
      ) {
        const dealId = (e.detail as { deal_id: number }).deal_id;
        showToast("Deal already exists — opening it", { type: "info" });
        navigate(`/deals/${dealId}`);
        return;
      }
      showToast(e instanceof Error ? e.message : "Error", { type: "error" });
    }
  };

  const handleCreativeMediaFile = async (file: File | null) => {
    if (!file) return;
    setMediaUploading(true);
    try {
      const uploaded = await uploadMedia(file);
      setCreativeMedia((prev) => [...prev, { type: uploaded.type, file_id: uploaded.file_id }]);
      showToast("File uploaded", { type: "success" });
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Upload error", { type: "error" });
    } finally {
      setMediaUploading(false);
    }
  };

  if (!id || Number.isNaN(listingId)) {
    return (
      <div className="flex flex-col items-center gap-3 py-12">
        <Text type="body" color="danger">Invalid listing</Text>
        <Button text="Back" type="secondary" onClick={() => navigate(-1)} />
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
        <Text type="body" color="danger">{error ?? "Listing not found"}</Text>
        <Button text="Back" type="secondary" onClick={() => navigate(-1)} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Text type="title2" weight="bold">
        Preview
      </Text>

      <Group header="Channel">
        <GroupItem
          text={channel?.title ?? (channel?.username ? `@${channel.username}` : `Channel #${listing.channel_id}`)}
          description={channel?.username ? `@${channel.username}` : "—"}
        />
      </Group>

      <Group header="Stats">
        <GroupItem
          text="Subscribers"
          after={<Text type="body">{formatNumber(stats?.subscribers ?? null)}</Text>}
        />
        <GroupItem
          text="Views per post"
          after={<Text type="body">{formatNumber(stats?.views_per_post ?? null)}</Text>}
        />
        <GroupItem
          text="Source"
          after={<Text type="body">{stats?.source ?? "—"}</Text>}
        />
      </Group>

      <Group header="Terms">
        <GroupItem
          text="Price (USD)"
          after={<Text type="body">{listing.price_usd != null ? `$${listing.price_usd}` : "—"}</Text>}
        />
        <GroupItem
          text="Price (TON)"
          after={<Text type="body">{listing.price_ton != null ? `${listing.price_ton}` : "—"}</Text>}
        />
        <GroupItem text="Format" after={<Text type="body">{listing.format}</Text>} />
        <GroupItem
          text="Categories"
          after={
            <Text type="body">
              {listing.categories?.length ? listing.categories.join(", ") : "—"}
            </Text>
          }
        />
      </Group>

      <Group header="Constraints">
        <GroupItem
          text="Language"
          after={
            <Text type="body">
              {(listing.constraints as Record<string, unknown> | null)?.lang
                ? String((listing.constraints as Record<string, unknown>).lang).toUpperCase()
                : "—"}
            </Text>
          }
        />
        <GroupItem
          text="Geo"
          after={
            <Text type="body">
              {Array.isArray((listing.constraints as Record<string, unknown> | null)?.geo) &&
              ((listing.constraints as Record<string, unknown>).geo as string[]).length > 0
                ? ((listing.constraints as Record<string, unknown>).geo as string[]).join(", ")
                : "—"}
            </Text>
          }
        />
      </Group>

      <Group header="Response">
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
            className="w-full text-sm"
            rows={4}
            placeholder={"Brief\nExample:\n- product\n- CTA\n- constraints"}
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
          />
          <textarea
            className="w-full text-sm"
            rows={3}
            placeholder="Creative example (text)"
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
              Files: {creativeMedia.map((item) => `${item.type}:${item.file_id.slice(0, 10)}...`).join(", ")}
            </Text>
          )}
          {mediaUploading && (
            <Text type="caption1" color="secondary">
              Uploading file...
            </Text>
          )}
        </div>
      </Group>

      <div className="flex flex-col gap-2 pt-2">
        <Button text="Respond" type="primary" onClick={respond} />
        <Button text="Back" type="secondary" onClick={() => navigate(-1)} />
      </div>
    </div>
  );
}
