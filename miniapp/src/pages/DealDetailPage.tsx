import { useCallback, useEffect, useState } from "react";
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
import { DealEventTimeline } from "../components/DealEventTimeline";
import { CollapsibleGroup } from "../components/CollapsibleGroup";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { FileUploadButton } from "../components/FileUploadButton";
import type { DealDetail, DealStatus, MediaFileId } from "../types";
import { useAuth } from "../contexts/AuthContext";
import { DateTimePickerField, localInputToIso, isoToLocalInput } from "../components/DateTimePickerField";

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

const STATUS_LABELS: Record<DealStatus, string> = {
  NEGOTIATING: "Negotiating",
  TERMS_LOCKED: "Terms Locked",
  AWAITING_PAYMENT: "Awaiting Payment",
  FUNDED: "Funded",
  CREATIVE_DRAFT: "Creative Draft",
  CREATIVE_REVIEW: "Creative Review",
  APPROVED: "Approved",
  SCHEDULED: "Scheduled",
  POSTED: "Posted",
  VERIFYING: "Verifying",
  RELEASED: "Released",
  REFUNDED: "Refunded",
  CANCELED: "Canceled",
};

type CreativePayload = {
  id: number;
  version: number;
  text: string | null;
  media_file_ids: Array<MediaFileId | string> | null;
  status: string;
};

type ConfirmAction = {
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm: () => void;
};

function getCta(status: DealStatus): { label: string; action: "pay" | "bot" | null } {
  switch (status) {
    case "TERMS_LOCKED":
      return { label: "Proceed to Payment", action: "pay" };
    case "AWAITING_PAYMENT":
      return { label: "Pay", action: "pay" };
    case "FUNDED":
    case "CREATIVE_DRAFT":
    case "CREATIVE_REVIEW":
    case "APPROVED":
    case "SCHEDULED":
      return { label: "Open Bot", action: "bot" };
    case "POSTED":
    case "VERIFYING":
      return { label: "Check in Bot", action: "bot" };
    default:
      return { label: "", action: null };
  }
}

function getWaitingHint(
  status: DealStatus,
  role: "owner" | "advertiser",
): string | null {
  if (role === "advertiser") {
    switch (status) {
      case "NEGOTIATING":
        return "Waiting for the channel owner to set deal terms";
      case "FUNDED":
      case "CREATIVE_DRAFT":
        return "Waiting for the channel owner to prepare the creative";
      case "APPROVED":
        return "Waiting for the channel owner to schedule the post";
      case "SCHEDULED":
        return "The post is scheduled, waiting for publication";
      case "POSTED":
      case "VERIFYING":
        return "Verification in progress";
      default:
        return null;
    }
  }
  if (role === "owner") {
    switch (status) {
      case "TERMS_LOCKED":
      case "AWAITING_PAYMENT":
        return "Waiting for the advertiser to pay";
      case "CREATIVE_REVIEW":
        return "Waiting for the advertiser to review the creative";
      default:
        return null;
    }
  }
  return null;
}

function formatDate(value: string | null | undefined) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US");
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("en-US");
}

function formatInt(value: number | null | undefined) {
  if (value == null) return "—";
  return value.toLocaleString("en-US");
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
  const [confirmAction, setConfirmAction] = useState<ConfirmAction | null>(null);

  const fetcher = useCallback(() => apiFetch<DealDetail>(`/deals/${id}`), [id]);
  const { data: deal, loading, error, refetch } = useApi(fetcher, [id]);

  useEffect(() => {
    if (!deal) return;
    if (deal.price != null) setTermsPrice(String(deal.price));
    if (deal.format) setTermsFormat(deal.format);
    if (deal.verification_window != null) setTermsWindow(String(deal.verification_window));
    if (deal.publish_at) setTermsPublishAt(isoToLocalInput(deal.publish_at));
  }, [deal]);

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
        <Text type="body" color="danger">{error ?? "Deal not found"}</Text>
        <Button text="Back" type="secondary" onClick={() => navigate(-1)} />
      </div>
    );
  }

  const cta = getCta(deal.status as DealStatus);
  const isAdvertiser = user?.id === deal.advertiser_id;
  const role: "owner" | "advertiser" = isAdvertiser ? "advertiser" : "owner";
  const status = deal.status as DealStatus;
  const canEditTerms = role === "owner" && (status === "NEGOTIATING" || status === "TERMS_LOCKED");
  const canSetPublishAt =
    role === "owner" &&
    !["NEGOTIATING", "TERMS_LOCKED", "POSTED", "VERIFYING", "RELEASED", "REFUNDED", "CANCELED"].includes(status);
  const canCreateCreative = role === "owner" && (status === "FUNDED" || status === "CREATIVE_DRAFT");
  const canReviewCreative = role === "advertiser" && status === "CREATIVE_REVIEW";
  const canSendBrief = role === "advertiser" && !["RELEASED", "REFUNDED", "CANCELED"].includes(status);
  const canViewCreative = CREATIVE_VIEW_STATUSES.has(status);
  const wizardSteps = [
    ...(canEditTerms ? [{ key: "terms", title: "Terms" }] : []),
    ...(canSetPublishAt ? [{ key: "workflow", title: "Date" }] : []),
    ...(canCreateCreative ? [{ key: "creative", title: "Creative" }] : []),
    ...(canReviewCreative ? [{ key: "review", title: "Review" }] : []),
    ...(canSendBrief ? [{ key: "brief", title: "Brief" }] : []),
    ...(canViewCreative ? [{ key: "view", title: "View" }] : []),
  ];
  const safeWizardStep = wizardSteps.length > 0 ? Math.min(wizardStep, wizardSteps.length - 1) : 0;
  const activeWizardStep = wizardSteps[safeWizardStep]?.key ?? null;
  const isStepVisible = (key: string) => wizardSteps.length === 0 || activeWizardStep === key;
  const waitingHint = getWaitingHint(status, role);
  const creativeStatusOptions = [
    { value: "APPROVED", label: "Approve" },
    { value: "DRAFT", label: "Request changes" },
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
        showToast("Telegram WebApp is not available", { type: "error" });
      }
    }
  };

  const handleOpenBot = () => {
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.openTelegramLink(`${BOT_URL}?start=deal_${deal.id}`);
    } else {
      showToast("Telegram WebApp is not available", { type: "error" });
    }
  };

  const handleOpenChannel = () => {
    if (!channelUsername) return;
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.openTelegramLink(`https://t.me/${channelUsername}`);
    } else {
      showToast("Telegram WebApp is not available", { type: "error" });
    }
  };

  const withSubmitting = async (action: () => Promise<void>) => {
    setSubmitting(true);
    try {
      await action();
      await refetch();
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Error", { type: "error" });
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
          throw new Error("Invalid publish date");
        }
        payload.publish_at = publishAtIso;
      }
      if (termsWindow.trim()) payload.verification_window = Number(termsWindow);
      if (
        (payload.price !== undefined && Number.isNaN(payload.price as number)) ||
        (payload.verification_window !== undefined && Number.isNaN(payload.verification_window as number))
      ) {
        throw new Error("Price and verification window must be numbers");
      }
      if (Object.keys(payload).length === 0) {
        throw new Error("Fill in at least one field");
      }
      await apiFetch(`/deals/${deal.id}/terms`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      showToast("Terms updated", { type: "success" });
    });
  };

  const handleLockTerms = () => {
    setConfirmAction({
      title: "Lock deal terms?",
      description: "This will fix the price, format, and publish date. You won't be able to change them later.",
      confirmLabel: "Lock Terms",
      onConfirm: () => {
        setConfirmAction(null);
        submitTerms();
      },
    });
  };

  const submitPublishAt = async () => {
    await withSubmitting(async () => {
      const publishAtIso = localInputToIso(publishAtValue);
      if (!publishAtIso) {
        throw new Error("Please specify publish date");
      }
      await apiFetch(`/deals/${deal.id}/publish_at`, {
        method: "POST",
        body: JSON.stringify({ publish_at: publishAtIso }),
      });
      showToast("Publish date updated", { type: "success" });
    });
  };

  const submitCreative = async () => {
    await withSubmitting(async () => {
      if (!creativeText.trim() && creativeMedia.length === 0) {
        throw new Error("Add text or media");
      }
      await apiFetch(`/deals/${deal.id}/creative`, {
        method: "POST",
        body: JSON.stringify({
          text: creativeText.trim() || null,
          media_file_ids: creativeMedia.length > 0 ? creativeMedia : null,
        }),
      });
      showToast("Creative submitted", { type: "success" });
      setCreativeText("");
      setCreativeMedia([]);
    });
  };

  const submitCreativeReview = async () => {
    await withSubmitting(async () => {
      if (!creativeStatus) {
        throw new Error("Select a creative status");
      }
      const publishAtIso = localInputToIso(creativePublishAt);
      if (creativePublishAt.trim() && !publishAtIso) {
        throw new Error("Invalid publish date");
      }
      await apiFetch(`/deals/${deal.id}/creative/status`, {
        method: "POST",
        body: JSON.stringify({
          status: creativeStatus,
          comment: creativeComment.trim() || null,
          publish_at: publishAtIso,
        }),
      });
      showToast("Review submitted", { type: "success" });
      setCreativeComment("");
    });
  };

  const submitBrief = async () => {
    await withSubmitting(async () => {
      const publishAtIso = localInputToIso(briefPublishAt);
      if (briefPublishAt.trim() && !publishAtIso) {
        throw new Error("Invalid publish date");
      }
      if (!briefText.trim() && !publishAtIso && briefMedia.length === 0) {
        throw new Error("Fill in brief or publish date");
      }
      await apiFetch(`/deals/${deal.id}/advertiser_brief`, {
        method: "POST",
        body: JSON.stringify({
          text: briefText.trim() || null,
          publish_at: publishAtIso,
          media_file_ids: briefMedia.length > 0 ? briefMedia : null,
        }),
      });
      showToast("Brief submitted", { type: "success" });
      setBriefText("");
      setBriefMedia([]);
    });
  };

  const handleCreativeFile = async (file: File) => {
    setCreativeUploading(true);
    try {
      const uploaded = await uploadMedia(file);
      setCreativeMedia((prev) => [...prev, { type: uploaded.type, file_id: uploaded.file_id }]);
      showToast("Media added", { type: "success" });
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Upload error", { type: "error" });
    } finally {
      setCreativeUploading(false);
    }
  };

  const handleBriefFile = async (file: File) => {
    setBriefUploading(true);
    try {
      const uploaded = await uploadMedia(file);
      setBriefMedia((prev) => [...prev, { type: uploaded.type, file_id: uploaded.file_id }]);
      showToast("Media added", { type: "success" });
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Upload error", { type: "error" });
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
      {/* Header */}
      <div className="flex items-center justify-between">
        <Text type="title2" weight="bold">
          Deal #{deal.id}
        </Text>
        <DealStatusBadge status={deal.status as DealStatus} />
      </div>

      {/* Channel (compact) */}
      <Group header="Channel">
        <GroupItem
          text="Channel"
          after={<Text type="body">{channelTitle}</Text>}
          description={
            <div className="flex flex-col gap-0.5">
              {channelUsername && (
                <Text type="caption1" color="secondary">
                  @{channelUsername}
                </Text>
              )}
              <Text type="caption1" color="secondary">
                Subscribers: {formatInt(deal.channel_info?.subscribers)} · Views/post:{" "}
                {formatInt(deal.channel_info?.views_per_post)}
              </Text>
            </div>
          }
          onClick={channelUsername ? handleOpenChannel : undefined}
          chevron={Boolean(channelUsername)}
        />
      </Group>

      {/* Key Details */}
      <Group header="Details">
        {deal.price != null && (
          <GroupItem text="Price" after={<Text type="body">${deal.price}</Text>} />
        )}
        <GroupItem
          text="Format"
          after={<Text type="body">{deal.format ?? "—"}</Text>}
        />
        <GroupItem
          text="Advertiser"
          after={
            <Text type="body">
              {deal.advertiser_info?.tg_username
                ? `@${deal.advertiser_info.tg_username.replace(/^@/, "")}`
                : "—"}
            </Text>
          }
        />
        <CollapsibleGroup header="Show details">
          <GroupItem text="Deal ID" after={<Text type="body">{deal.id}</Text>} />
          <GroupItem
            text="Listing"
            after={<Text type="body">{deal.listing_id ?? "—"}</Text>}
          />
          <GroupItem
            text="Request"
            after={<Text type="body">{deal.request_id ?? "—"}</Text>}
          />
          <GroupItem text="Created" after={<Text type="body">{formatDateTime(deal.created_at)}</Text>} />
          <GroupItem text="Updated" after={<Text type="body">{formatDateTime(deal.updated_at)}</Text>} />
        </CollapsibleGroup>
      </Group>

      {/* Publishing & Verification (collapsed) */}
      <Group>
        <CollapsibleGroup header="Publishing & Verification">
          <GroupItem text="Publish (planned)" after={<Text type="body">{formatDate(deal.publish_at)}</Text>} />
          <GroupItem text="Publish (actual)" after={<Text type="body">{formatDateTime(deal.posted_at)}</Text>} />
          <GroupItem
            text="Message ID"
            after={<Text type="body">{deal.posted_message_id ?? "—"}</Text>}
          />
          <GroupItem
            text="Verification window"
            after={
              <Text type="body">
                {deal.verification_window != null ? `${deal.verification_window} min` : "—"}
              </Text>
            }
          />
          <GroupItem
            text="Verification started"
            after={<Text type="body">{formatDateTime(deal.verification_started_at)}</Text>}
          />
        </CollapsibleGroup>
      </Group>

      {/* Brief */}
      {deal.brief && (
        <Group header="Brief">
          <div className="px-4 py-3">
            <Text type="body" color="secondary">
              {deal.brief}
            </Text>
          </div>
        </Group>
      )}
      {/* Waiting hint */}
      {waitingHint && (
        <div
          className="flex items-center gap-3 rounded-xl px-4 py-3"
          style={{
            backgroundColor: "var(--tg-theme-secondary-bg-color, #2c2c2e)",
          }}
        >
          <span className="text-base leading-none" aria-hidden>&#9202;</span>
          <Text type="body" color="secondary">
            {waitingHint}
          </Text>
        </div>
      )}


      {/* Deal Terms */}
      {canEditTerms && isStepVisible("terms") && (
        <Group header="Deal Terms">
          <div className="flex flex-col gap-3 px-4 py-3">
            <div className="flex flex-col gap-1">
              <Text type="caption1" color="secondary">Price, $</Text>
              <Input
                placeholder="0.00"
                type="text"
                value={termsPrice}
                onChange={(v) => setTermsPrice(v)}
                numeric
              />
            </div>
            <div className="flex flex-col gap-1">
              <Text type="caption1" color="secondary">Format</Text>
              <Input
                placeholder="post, repost, story..."
                type="text"
                value={termsFormat}
                onChange={(v) => setTermsFormat(v)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <Text type="caption1" color="secondary">Publish date</Text>
              <DateTimePickerField value={termsPublishAt} onChange={setTermsPublishAt} />
            </div>
            <div className="flex flex-col gap-1">
              <Text type="caption1" color="secondary">Verification window, min</Text>
              <Input
                placeholder="10"
                type="number"
                value={termsWindow}
                onChange={(v) => setTermsWindow(v.replace(/[^0-9]/g, ""))}
                numeric
              />
            </div>
            <Button text="Lock Terms" type="primary" loading={submitting} onClick={handleLockTerms} />
          </div>
        </Group>
      )}

      {/* Publish Date */}
      {canSetPublishAt && isStepVisible("workflow") && (
        <Group header="Publish Date">
          <div className="flex flex-col gap-3 px-4 py-3">
            <div className="flex flex-col gap-1">
              <Text type="caption1" color="secondary">Publish date</Text>
              <DateTimePickerField value={publishAtValue} onChange={setPublishAtValue} allowEmpty={false} />
            </div>
            <Button text="Update Date" type="secondary" loading={submitting} onClick={submitPublishAt} />
          </div>
        </Group>
      )}

      {/* Creative */}
      {canCreateCreative && isStepVisible("creative") && (
        <Group header="Creative">
          <div className="flex flex-col gap-3 px-4 py-3">
            <div className="flex flex-col gap-1">
              <Text type="caption1" color="secondary">Creative text</Text>
              <textarea
                className="w-full text-sm"
                rows={4}
                placeholder="Enter the creative text for the post..."
                value={creativeText}
                onChange={(e) => setCreativeText(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <Text type="caption1" color="secondary">Media files</Text>
              <FileUploadButton
                files={creativeMedia}
                onChange={setCreativeMedia}
                onUpload={handleCreativeFile}
                uploading={creativeUploading}
              />
            </div>
            <Button text="Submit Creative" type="primary" loading={submitting} onClick={submitCreative} />
          </div>
        </Group>
      )}

      {/* Creative Review */}
      {canReviewCreative && isStepVisible("review") && (
        <Group header="Creative Review">
          <div className="flex flex-col gap-3 px-4 py-3">
            <div className="flex flex-col gap-1">
              <Text type="caption1" color="secondary">Decision</Text>
              <Select options={creativeStatusOptions} value={creativeStatus} onChange={(v) => setCreativeStatus(v)} />
            </div>
            <div className="flex flex-col gap-1">
              <Text type="caption1" color="secondary">Comment</Text>
              <textarea
                className="w-full text-sm"
                rows={3}
                placeholder="Revision notes or feedback..."
                value={creativeComment}
                onChange={(e) => setCreativeComment(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <Text type="caption1" color="secondary">Publish date</Text>
              <DateTimePickerField value={creativePublishAt} onChange={setCreativePublishAt} />
            </div>
            <Button text="Submit Review" type="primary" loading={submitting} onClick={submitCreativeReview} />
          </div>
        </Group>
      )}

      {/* Advertiser Brief */}
      {canSendBrief && isStepVisible("brief") && (
        <Group header="Advertiser Brief">
          <div className="flex flex-col gap-3 px-4 py-3">
            <div className="flex flex-col gap-1">
              <Text type="caption1" color="secondary">Brief</Text>
              <textarea
                className="w-full text-sm"
                rows={4}
                placeholder="Product, CTA, constraints..."
                value={briefText}
                onChange={(e) => setBriefText(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <Text type="caption1" color="secondary">Preferred publish date</Text>
              <DateTimePickerField value={briefPublishAt} onChange={setBriefPublishAt} />
            </div>
            <div className="flex flex-col gap-1">
              <Text type="caption1" color="secondary">Attachments</Text>
              <FileUploadButton
                files={briefMedia}
                onChange={setBriefMedia}
                onUpload={handleBriefFile}
                uploading={briefUploading}
              />
            </div>
            <Button text="Submit Brief" type="secondary" loading={submitting} onClick={submitBrief} />
          </div>
        </Group>
      )}

      {/* View Creative */}
      {canViewCreative && isStepVisible("view") && (
        <Group header="View Creative">
          <div className="flex flex-col gap-3 px-4 py-3">
            <Button text="Show Latest Creative" type="secondary" loading={submitting} onClick={loadCreative} />
            {creativeData && (
              <div className="flex flex-col gap-2 rounded-xl border border-[var(--tg-theme-hint-color,#ccc)] p-3">
                <Text type="body">Version: {creativeData.version}</Text>
                <Text type="body">Status: {creativeData.status}</Text>
                <Text type="body" color="secondary">
                  {creativeData.text || "No text"}
                </Text>
                {creativeData.media_file_ids && creativeData.media_file_ids.length > 0 && (
                  <Text type="caption1" color="secondary">
                    {creativeData.media_file_ids.length} media file(s) attached
                  </Text>
                )}
              </div>
            )}
          </div>
        </Group>
      )}

      {/* CTA (right after forms) */}
      <div className="flex flex-col gap-2 pt-2">
        {cta.action && (
          <Button text={cta.label} type="primary" onClick={handleCta} />
        )}
        <button
          type="button"
          className="py-2 text-center text-sm"
          style={{ color: "var(--tg-theme-link-color, #3b82f6)" }}
          onClick={handleOpenBot}
        >
          Open Bot
        </button>
      </div>

      {/* Tampered / Deleted warnings */}
      {deal.tampered && (
        <Group>
          <div className="px-4 py-3">
            <Text type="body" color="danger">
              Post was modified after publishing
            </Text>
          </div>
        </Group>
      )}

      {deal.deleted && (
        <Group>
          <div className="px-4 py-3">
            <Text type="body" color="danger">
              Post was deleted
            </Text>
          </div>
        </Group>
      )}

      {/* Event History (bottom) */}
      <Group header="Event History">
        <DealEventTimeline dealId={deal.id} />
      </Group>

      {/* Confirm Dialog */}
      <ConfirmDialog
        open={confirmAction !== null}
        title={confirmAction?.title ?? ""}
        description={confirmAction?.description}
        confirmLabel={confirmAction?.confirmLabel}
        onConfirm={() => confirmAction?.onConfirm()}
        onCancel={() => setConfirmAction(null)}
      />
    </div>
  );
}
