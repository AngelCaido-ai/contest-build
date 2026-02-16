import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Group, Input, Text, useToast } from "@telegram-tools/ui-kit";
import { apiFetch } from "../api/client";
import { useBackButton } from "../hooks/useBackButton";

type AddMode = "username" | "chat_id";

export function AddChannelPage() {
  useBackButton();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [mode, setMode] = useState<AddMode>("username");
  const [tgChatId, setTgChatId] = useState("");
  const [username, setUsername] = useState("");
  const [title, setTitle] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    if (mode === "username") {
      if (!username.trim()) {
        showToast("Please enter the channel username", { type: "error" });
        return;
      }
    } else {
      if (!tgChatId.trim()) {
        showToast("Please enter the channel Chat ID", { type: "error" });
        return;
      }
      const parsedId = Number(tgChatId.trim());
      if (Number.isNaN(parsedId)) {
        showToast("Chat ID must be a number", { type: "error" });
        return;
      }
    }

    setSubmitting(true);
    try {
      const body: Record<string, unknown> = { bot_admin_status: true };
      if (mode === "username") {
        body.username = username.trim();
      } else {
        body.tg_chat_id = Number(tgChatId.trim());
        if (username.trim()) body.username = username.trim();
      }
      if (title.trim()) body.title = title.trim();

      await apiFetch("/channels", {
        method: "POST",
        body: JSON.stringify(body),
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

      <div
        className="flex rounded-lg overflow-hidden border border-[var(--tg-theme-hint-color,#ccc)]"
      >
        <button
          className={`flex-1 py-2 text-sm font-medium transition-colors ${
            mode === "username"
              ? "bg-[var(--tg-theme-button-color,#3390ec)] text-[var(--tg-theme-button-text-color,#fff)]"
              : "bg-[var(--tg-theme-secondary-bg-color,#f0f0f0)] text-[var(--tg-theme-text-color,#000)]"
          }`}
          onClick={() => setMode("username")}
        >
          By Username
        </button>
        <button
          className={`flex-1 py-2 text-sm font-medium transition-colors ${
            mode === "chat_id"
              ? "bg-[var(--tg-theme-button-color,#3390ec)] text-[var(--tg-theme-button-text-color,#fff)]"
              : "bg-[var(--tg-theme-secondary-bg-color,#f0f0f0)] text-[var(--tg-theme-text-color,#000)]"
          }`}
          onClick={() => setMode("chat_id")}
        >
          By Chat ID
        </button>
      </div>

      <Group header="Channel Data">
        <div className="flex flex-col gap-3 px-4 py-3">
          {mode === "username" ? (
            <Input
              placeholder="@username (e.g. @mychannel)"
              type="text"
              value={username}
              onChange={(v) => setUsername(v)}
            />
          ) : (
            <>
              <Input
                placeholder="Chat ID (e.g. -1001234567890)"
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
            </>
          )}
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
