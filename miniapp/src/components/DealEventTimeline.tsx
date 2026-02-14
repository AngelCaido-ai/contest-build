import { useCallback, useState } from "react";
import { Text, Button, Spinner } from "@telegram-tools/ui-kit";
import { apiFetch } from "../api/client";
import { useApi } from "../hooks/useApi";
import type { DealEvent, DealStatus } from "../types";

const EVENT_LABELS: Record<string, { label: string; icon: string }> = {
  DEAL_CREATED: { label: "Deal created", icon: "🆕" },
  TERMS_LOCKED: { label: "Terms locked", icon: "🔒" },
  STATUS_UPDATED: { label: "Status updated", icon: "🔄" },
  PUBLISH_AT_UPDATED: { label: "Publish date updated", icon: "📅" },
  PUBLISH_AT_REQUESTED: { label: "Publish date requested", icon: "📅" },
  CREATIVE_SUBMITTED: { label: "Creative submitted", icon: "🎨" },
  CREATIVE_STATUS: { label: "Creative status", icon: "✏️" },
  ADVERTISER_BRIEF: { label: "Advertiser brief", icon: "📋" },
};

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

function formatEventDate(value: string) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const isYesterday = d.toDateString() === yesterday.toDateString();

  const time = d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
  if (isToday) return `Today, ${time}`;
  if (isYesterday) return `Yesterday, ${time}`;
  return d.toLocaleDateString("en-US", { day: "numeric", month: "short" }) + `, ${time}`;
}

function renderPayloadDetails(type: string, payload: DealEvent["payload"]) {
  if (!payload) return null;

  const details: string[] = [];

  if (type === "TERMS_LOCKED") {
    if (payload.price != null) details.push(`Price: $${payload.price}`);
    if (payload.format) details.push(`Format: ${payload.format}`);
    if (payload.publish_at) details.push(`Date: ${new Date(payload.publish_at as string).toLocaleDateString("en-US")}`);
    if (payload.verification_window) details.push(`Verification window: ${payload.verification_window} min`);
  } else if (type === "STATUS_UPDATED" && payload.status) {
    const label = STATUS_LABELS[payload.status as DealStatus] ?? payload.status;
    details.push(`→ ${label}`);
  } else if (type === "CREATIVE_SUBMITTED" && payload.version) {
    details.push(`Version ${payload.version}`);
  } else if (type === "CREATIVE_STATUS") {
    if (payload.status === "APPROVED") details.push("Approved");
    else if (payload.status === "DRAFT") details.push("Sent for revision");
    if (payload.comment) details.push(`«${payload.comment}»`);
    if (payload.publish_at) details.push(`Date: ${new Date(payload.publish_at as string).toLocaleDateString("en-US")}`);
  } else if (type === "PUBLISH_AT_UPDATED" || type === "PUBLISH_AT_REQUESTED") {
    if (payload.publish_at) details.push(new Date(payload.publish_at as string).toLocaleDateString("en-US"));
  } else if (type === "ADVERTISER_BRIEF") {
    if (payload.text) details.push(String(payload.text).length > 80 ? String(payload.text).slice(0, 80) + "…" : String(payload.text));
    if (payload.publish_at) details.push(`Date: ${new Date(payload.publish_at as string).toLocaleDateString("en-US")}`);
    if (Array.isArray(payload.media_file_ids) && payload.media_file_ids.length > 0) {
      details.push(`${payload.media_file_ids.length} file(s)`);
    }
  } else {
    try {
      const text = JSON.stringify(payload);
      if (text !== "{}" && text.length <= 120) details.push(text);
    } catch { /* ignore */ }
  }

  if (details.length === 0) return null;

  return (
    <div className="flex flex-col gap-0.5 mt-0.5">
      {details.map((detail, i) => (
        <Text key={i} type="caption1" color="secondary">
          {detail}
        </Text>
      ))}
    </div>
  );
}

function getEventColor(type: string): string {
  switch (type) {
    case "DEAL_CREATED": return "#3b82f6";
    case "TERMS_LOCKED": return "#6366f1";
    case "STATUS_UPDATED": return "#8b5cf6";
    case "CREATIVE_SUBMITTED": return "#a855f7";
    case "CREATIVE_STATUS": return "#22c55e";
    case "ADVERTISER_BRIEF": return "#f59e0b";
    case "PUBLISH_AT_UPDATED":
    case "PUBLISH_AT_REQUESTED": return "#06b6d4";
    default: return "#6b7280";
  }
}

type Props = {
  dealId: number;
};

export function DealEventTimeline({ dealId }: Props) {
  const [expanded, setExpanded] = useState(false);

  const fetcher = useCallback(() => apiFetch<DealEvent[]>(`/deals/${dealId}/events`), [dealId]);
  const { data: events, loading, error } = useApi(fetcher, [dealId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-6">
        <Spinner size="24px" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="px-4 py-3">
        <Text type="body" color="danger">{error}</Text>
      </div>
    );
  }

  if (!events || events.length === 0) {
    return (
      <div className="px-4 py-3">
        <Text type="body" color="secondary">No events</Text>
      </div>
    );
  }

  const visibleEvents = expanded ? events : events.slice(0, 5);
  const hasMore = events.length > 5;

  return (
    <div className="flex flex-col">
      <div className="relative flex flex-col">
        {visibleEvents.map((ev, idx) => {
          const config = EVENT_LABELS[ev.type] ?? { label: ev.type, icon: "•" };
          const color = getEventColor(ev.type);
          const isLast = idx === visibleEvents.length - 1;

          return (
            <div key={ev.id} className="flex gap-3 relative">
              <div className="flex flex-col items-center" style={{ width: 24 }}>
                <div
                  className="w-3 h-3 rounded-full shrink-0 mt-1 z-10"
                  style={{ backgroundColor: color }}
                />
                {!isLast && (
                  <div
                    className="w-px flex-1"
                    style={{ backgroundColor: "var(--tg-theme-hint-color, #ccc)", opacity: 0.3 }}
                  />
                )}
              </div>
              <div className={`flex flex-col pb-4 min-w-0 flex-1 ${isLast ? "" : ""}`}>
                <div className="flex items-center gap-1.5">
                  <Text type="caption1">{config.icon}</Text>
                  <Text type="body" weight="medium">{config.label}</Text>
                </div>
                <Text type="caption1" color="secondary">{formatEventDate(ev.created_at)}</Text>
                {renderPayloadDetails(ev.type, ev.payload)}
              </div>
            </div>
          );
        })}
      </div>

      {hasMore && !expanded && (
        <div className="pt-1 pb-2 px-4">
          <Button
            text={`Show all (${events.length})`}
            type="secondary"
            onClick={() => setExpanded(true)}
          />
        </div>
      )}
    </div>
  );
}
