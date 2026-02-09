import { useState, useCallback } from "react";
import {
  Text,
  Input,
  Button,
  Group,
  GroupItem,
  SkeletonElement,
  useToast,
} from "@telegram-tools/ui-kit";
import { apiFetch } from "../api/client";
import { useApi } from "../hooks/useApi";
import { EmptyState } from "../components/EmptyState";
import type { Channel, Manager } from "../types";

export function ChannelsPage() {
  const { showToast } = useToast();

  const [selectedChannelId, setSelectedChannelId] = useState<number | null>(null);
  const [managers, setManagers] = useState<Manager[]>([]);
  const [managersLoading, setManagersLoading] = useState(false);
  const [managerUsername, setManagerUsername] = useState("");

  const fetchChannels = useCallback(() => apiFetch<Channel[]>("/channels"), []);
  const { data: channels, loading } = useApi(fetchChannels, []);

  const loadManagers = async (channelId: number) => {
    setManagersLoading(true);
    try {
      const items = await apiFetch<Manager[]>(`/channels/${channelId}/managers`);
      setManagers(items);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка", { type: "error" });
    } finally {
      setManagersLoading(false);
    }
  };

  const selectChannel = (id: number) => {
    setSelectedChannelId(id);
    loadManagers(id);
  };

  const refreshStats = async (channelId: number) => {
    try {
      await apiFetch(`/stats/channels/${channelId}/refresh`, { method: "POST" });
      showToast("Статистика обновлена", { type: "success" });
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка", { type: "error" });
    }
  };

  const addManager = async () => {
    if (!selectedChannelId) return;
    const username = managerUsername.trim();
    if (!username) {
      showToast("Введите @username", { type: "error" });
      return;
    }
    try {
      await apiFetch(`/channels/${selectedChannelId}/managers`, {
        method: "POST",
        body: JSON.stringify({ tg_username: username }),
      });
      setManagerUsername("");
      showToast("Менеджер добавлен", { type: "success" });
      await loadManagers(selectedChannelId);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка", { type: "error" });
    }
  };

  const removeManager = async (managerId: number) => {
    if (!selectedChannelId) return;
    try {
      await apiFetch(`/channels/${selectedChannelId}/managers/${managerId}`, {
        method: "DELETE",
      });
      showToast("Менеджер удален", { type: "success" });
      await loadManagers(selectedChannelId);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка", { type: "error" });
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Text type="title2" weight="bold">
        Мои каналы
      </Text>

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
          title="Нет каналов"
          description="Добавьте канал через бота"
        />
      )}

      {!loading && channels && channels.length > 0 && (
        <Group header="Каналы">
          {channels.map((ch) => (
            <GroupItem
              key={ch.id}
              text={ch.title ?? ch.username ?? `#${ch.tg_chat_id}`}
              description={
                ch.stats
                  ? `${ch.stats.subscribers ?? "?"} подписчиков · ${ch.stats.views_per_post ?? "?"} просмотров`
                  : "Статистика не загружена"
              }
              after={
                <Button
                  text="Обновить"
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

      {selectedChannelId && (
        <>
          <Group header="Менеджеры">
            <div className="flex gap-2 px-4 py-2">
              <Input
                placeholder="@username"
                value={managerUsername}
                onChange={(v) => setManagerUsername(v)}
              />
              <Button text="Добавить" type="primary" onClick={addManager} />
            </div>
          </Group>

          {managersLoading && (
            <Group>
              <GroupItem
                text={<SkeletonElement style={{ width: "50%", height: 16 }} />}
              />
            </Group>
          )}

          {!managersLoading && managers.length === 0 && (
            <EmptyState icon="👤" title="Нет менеджеров" />
          )}

          {!managersLoading && managers.length > 0 && (
            <Group>
              {managers.map((m) => (
                <GroupItem
                  key={m.id}
                  text={m.tg_username ? `@${m.tg_username}` : `User #${m.tg_user_id}`}
                  after={
                    <Button
                      text="Удалить"
                      type="secondary"
                      onClick={() => removeManager(m.id)}
                    />
                  }
                />
              ))}
            </Group>
          )}
        </>
      )}
    </div>
  );
}
