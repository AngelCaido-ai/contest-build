import { useState, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Text,
  Button,
  Group,
  GroupItem,
  SkeletonElement,
  useToast,
} from "@telegram-tools/ui-kit";
import { apiFetch } from "../api/client";
import { useApi } from "../hooks/useApi";
import { useAuth } from "../contexts/AuthContext";
import { EmptyState } from "../components/EmptyState";
import type { Channel, Manager, TgAdmin } from "../types";

export function ChannelsPage() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { user } = useAuth();

  const [selectedChannelId, setSelectedChannelId] = useState<number | null>(null);
  const [managers, setManagers] = useState<Manager[]>([]);
  const [managersLoading, setManagersLoading] = useState(false);
  const [tgAdmins, setTgAdmins] = useState<TgAdmin[]>([]);
  const [adminsLoading, setAdminsLoading] = useState(false);

  const fetchChannels = useCallback(() => apiFetch<Channel[]>("/channels"), []);
  const { data: channels, loading, refetch } = useApi(fetchChannels, []);

  const selectedChannel = useMemo(
    () => channels?.find((ch) => ch.id === selectedChannelId) ?? null,
    [channels, selectedChannelId],
  );
  const isOwner = selectedChannel !== null && selectedChannel.owner_user_id === user?.id;

  const managerTgIds = useMemo(
    () => new Set(managers.map((m) => m.tg_user_id)),
    [managers],
  );

  const availableAdmins = useMemo(
    () => tgAdmins.filter((a) => !managerTgIds.has(a.tg_user_id)),
    [tgAdmins, managerTgIds],
  );

  const loadManagers = async (channelId: number) => {
    setManagersLoading(true);
    try {
      const items = await apiFetch<Manager[]>(`/channels/${channelId}/managers`);
      setManagers(items);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Error", { type: "error" });
    } finally {
      setManagersLoading(false);
    }
  };

  const loadTgAdmins = async (channelId: number) => {
    setAdminsLoading(true);
    try {
      const items = await apiFetch<TgAdmin[]>(`/channels/${channelId}/tg-admins`);
      setTgAdmins(items);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Error", { type: "error" });
    } finally {
      setAdminsLoading(false);
    }
  };

  const selectChannel = (id: number) => {
    setSelectedChannelId(id);
    const ch = channels?.find((c) => c.id === id);
    if (ch && ch.owner_user_id === user?.id) {
      loadManagers(id);
      loadTgAdmins(id);
    } else {
      setManagers([]);
      setTgAdmins([]);
    }
  };

  const refreshStats = async (channelId: number) => {
    try {
      await apiFetch(`/stats/channels/${channelId}/refresh`, { method: "POST" });
      showToast("Stats updated", { type: "success" });
      refetch();
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Error", { type: "error" });
    }
  };

  const addManager = async (admin: TgAdmin) => {
    if (!selectedChannelId) return;
    try {
      await apiFetch(`/channels/${selectedChannelId}/managers`, {
        method: "POST",
        body: JSON.stringify({ tg_user_id: admin.tg_user_id }),
      });
      showToast("Manager added", { type: "success" });
      await loadManagers(selectedChannelId);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Error", { type: "error" });
    }
  };

  const removeManager = async (managerId: number) => {
    if (!selectedChannelId) return;
    try {
      await apiFetch(`/channels/${selectedChannelId}/managers/${managerId}`, {
        method: "DELETE",
      });
      showToast("Manager removed", { type: "success" });
      await loadManagers(selectedChannelId);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Error", { type: "error" });
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Text type="title2" weight="bold">
        My Channels
      </Text>
      <div className="flex gap-2">
        <Button text="Add Channel" type="primary" onClick={() => navigate("/channels/new")} />
        <Button text="Wallet" type="secondary" onClick={() => navigate("/wallet")} />
      </div>

      {loading && (
        <Group>
          {[1, 2].map((i) => (
            <GroupItem
              key={i}
              text={<SkeletonElement style={{ width: "50%", height: 16 }} />}
              description={<SkeletonElement style={{ width: "70%", height: 12 }} />}
            />
          ))}
        </Group>
      )}

      {!loading && (!channels || channels.length === 0) && (
        <EmptyState
          icon="📺"
          title="No channels"
          description="Add a channel via the miniapp"
        />
      )}

      {!loading && channels && channels.length > 0 && (
        <Group header="Channels">
          {channels.map((ch) => (
            <GroupItem
              key={ch.id}
              text={ch.title ?? ch.username ?? `#${ch.tg_chat_id}`}
              description={
                ch.stats
                  ? `${ch.stats.subscribers ?? "?"} subscribers · ${ch.stats.views_per_post ?? "?"} views`
                  : "Stats not loaded"
              }
              after={
                <Button
                  text="Refresh"
                  type="secondary"
                  onClick={() => refreshStats(ch.id)}
                />
              }
              onClick={() => selectChannel(ch.id)}
              chevron
            />
          ))}
        </Group>
      )}

      {selectedChannelId && isOwner && (
        <>
          {managersLoading ? (
            <Group header="Managers">
              <GroupItem
                text={<SkeletonElement style={{ width: "50%", height: 16 }} />}
              />
            </Group>
          ) : managers.length === 0 ? (
            <EmptyState icon="👤" title="No managers" />
          ) : (
            <Group header="Managers">
              {managers.map((m) => (
                <GroupItem
                  key={m.id}
                  text={m.tg_username ? `@${m.tg_username}` : `User #${m.tg_user_id}`}
                  after={
                    <Button
                      text="Remove"
                      type="secondary"
                      onClick={() => removeManager(m.id)}
                    />
                  }
                />
              ))}
            </Group>
          )}

          {adminsLoading ? (
            <Group header="Channel Admins">
              <GroupItem
                text={<SkeletonElement style={{ width: "50%", height: 16 }} />}
              />
            </Group>
          ) : availableAdmins.length > 0 ? (
            <Group header="Channel Admins">
              {availableAdmins.map((a) => (
                <GroupItem
                  key={a.tg_user_id}
                  text={a.first_name}
                  description={
                    a.tg_username
                      ? `@${a.tg_username} · ${a.status === "creator" ? "owner" : "admin"}`
                      : a.status === "creator"
                        ? "owner"
                        : "admin"
                  }
                  after={
                    <Button
                      text="Assign"
                      type="primary"
                      onClick={() => addManager(a)}
                    />
                  }
                />
              ))}
            </Group>
          ) : !adminsLoading && tgAdmins.length > 0 ? (
            <Text
              type="caption"
              style={{ color: "var(--tg-theme-hint-color)", textAlign: "center" }}
            >
              All channel admins are already assigned as managers
            </Text>
          ) : null}
        </>
      )}
    </div>
  );
}
