import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Group, Input, Text, useToast } from "@telegram-tools/ui-kit";
import { apiFetch } from "../api/client";
import { useBackButton } from "../hooks/useBackButton";

export function AddChannelPage() {
  useBackButton();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [tgChatId, setTgChatId] = useState("");
  const [username, setUsername] = useState("");
  const [title, setTitle] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    if (!tgChatId.trim()) {
      showToast("Please enter the channel tg_chat_id", { type: "error" });
      return;
    }
    const parsedId = Number(tgChatId.trim());
    if (Number.isNaN(parsedId)) {
      showToast("tg_chat_id must be a number", { type: "error" });
      return;
    }
    setSubmitting(true);
    try {
      await apiFetch("/channels", {
        method: "POST",
        body: JSON.stringify({
          tg_chat_id: parsedId,
          username: username.trim() || null,
          title: title.trim() || null,
          bot_admin_status: true,
        }),
      });
      showToast("Channel added", { type: "success" });
      navigate("/channels");
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Error", { type: "error" });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Text type="title2" weight="bold">
        Add Channel
      </Text>

      <Group header="Channel Data">
        <div className="flex flex-col gap-3 px-4 py-3">
          <Input
            placeholder="tg_chat_id (e.g. -100123...)"
            type="text"
            value={tgChatId}
            onChange={(v) => setTgChatId(v)}
          />
          <Input
            placeholder="Channel username (optional)"
            type="text"
            value={username}
            onChange={(v) => setUsername(v)}
          />
          <Input
            placeholder="Channel name (optional)"
            type="text"
            value={title}
            onChange={(v) => setTitle(v)}
          />
          <Text type="caption1" color="secondary">
            Before adding, make sure the bot is an admin of the channel.
          </Text>
        </div>
      </Group>

      <div className="flex flex-col gap-2">
        <Button text="Add Channel" type="primary" loading={submitting} onClick={submit} />
        <Button text="Back" type="secondary" onClick={() => navigate(-1)} />
      </div>
    </div>
  );
}
