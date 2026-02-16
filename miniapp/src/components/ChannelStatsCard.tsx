import { Group, GroupItem, Text } from "@telegram-tools/ui-kit";
import type { ChannelStats } from "../types";

function formatNumber(value: number | null | undefined): string {
  if (value == null) return "—";
  if (Number.isInteger(value) || value >= 100) {
    return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
  }
  return new Intl.NumberFormat("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(value);
}

function TrendIndicator({
  current,
  previous,
}: {
  current: number | null | undefined;
  previous: number | null | undefined;
}) {
  if (current == null || previous == null || previous === 0) return null;
  const diff = current - previous;
  if (diff === 0) return null;
  const pct = Math.abs(Math.round((diff / previous) * 100));
  const isUp = diff > 0;
  return (
    <span
      style={{
        color: isUp
          ? "var(--tg-theme-accent-text-color, #34c759)"
          : "var(--tg-theme-destructive-text-color, #e53935)",
        fontSize: 12,
        fontWeight: 600,
        marginLeft: 6,
      }}
    >
      {isUp ? "\u25B2" : "\u25BC"} {pct}%
    </span>
  );
}

function isRawStatsGraph(languages: Record<string, unknown>): boolean {
  return "_" in languages && typeof languages["_"] === "string";
}

function LanguageChips({ languages }: { languages: Record<string, unknown> }) {
  if (isRawStatsGraph(languages)) return <Text type="body">—</Text>;

  const entries = Object.entries(languages)
    .filter(([, v]) => typeof v === "number")
    .sort((a, b) => Number(b[1]) - Number(a[1]))
    .slice(0, 6);

  if (entries.length === 0) return <Text type="body">—</Text>;

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
      {entries.map(([lang, val]) => (
        <span
          key={lang}
          style={{
            display: "inline-block",
            padding: "2px 8px",
            borderRadius: 10,
            fontSize: 12,
            fontWeight: 500,
            backgroundColor: "var(--tg-theme-secondary-bg-color, #2c2c2e)",
            color: "var(--tg-theme-text-color, #fff)",
          }}
        >
          {lang.toUpperCase()} {typeof val === "number" ? `${Math.round(val * 100)}%` : val}
        </span>
      ))}
    </div>
  );
}

type Props = {
  stats: ChannelStats | null | undefined;
  compact?: boolean;
};

export function ChannelStatsCard({ stats, compact = false }: Props) {
  if (!stats) {
    return (
      <Group header="Stats">
        <GroupItem text="Stats not loaded" />
      </Group>
    );
  }

  if (compact) {
    return (
      <Text type="caption1" color="secondary">
        {formatNumber(stats.subscribers)} subscribers
        <TrendIndicator current={stats.subscribers} previous={stats.subscribers_prev} />
        {" · "}
        {formatNumber(stats.views_per_post)} views
        <TrendIndicator current={stats.views_per_post} previous={stats.views_per_post_prev} />
        {stats.shares_per_post != null && (
          <>
            {" · "}
            {formatNumber(stats.shares_per_post)} shares
          </>
        )}
        {stats.reactions_per_post != null && (
          <>
            {" · "}
            {formatNumber(stats.reactions_per_post)} reactions
          </>
        )}
      </Text>
    );
  }

  return (
    <Group header="Stats">
      <GroupItem
        text="Subscribers"
        after={
          <Text type="body">
            {formatNumber(stats.subscribers)}
            <TrendIndicator
              current={stats.subscribers}
              previous={stats.subscribers_prev}
            />
          </Text>
        }
      />
      <GroupItem
        text="Views per post"
        after={
          <Text type="body">
            {formatNumber(stats.views_per_post)}
            <TrendIndicator
              current={stats.views_per_post}
              previous={stats.views_per_post_prev}
            />
          </Text>
        }
      />
      <GroupItem
        text="Shares per post"
        after={
          <Text type="body">
            {formatNumber(stats.shares_per_post)}
            <TrendIndicator
              current={stats.shares_per_post}
              previous={stats.shares_per_post_prev}
            />
          </Text>
        }
      />
      <GroupItem
        text="Reactions per post"
        after={
          <Text type="body">
            {formatNumber(stats.reactions_per_post)}
            <TrendIndicator
              current={stats.reactions_per_post}
              previous={stats.reactions_per_post_prev}
            />
          </Text>
        }
      />
      {stats.enabled_notifications != null && (
        <GroupItem
          text="Notifications enabled"
          after={
            <Text type="body">
              {Math.round(stats.enabled_notifications * 100)}%
            </Text>
          }
        />
      )}
      {stats.languages_json && Object.keys(stats.languages_json).length > 0 && (
        <GroupItem
          text="Languages"
          after={<LanguageChips languages={stats.languages_json} />}
        />
      )}
      <GroupItem
        text="Source"
        after={<Text type="body">{stats.source ?? "—"}</Text>}
      />
    </Group>
  );
}
