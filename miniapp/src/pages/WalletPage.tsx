import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Group, Input, Text, useToast } from "@telegram-tools/ui-kit";
import { apiFetch } from "../api/client";
import { useBackButton } from "../hooks/useBackButton";
import { useAuth } from "../contexts/AuthContext";

type ProfileResponse = {
  id: number;
  linked_wallet: string | null;
};

export function WalletPage() {
  useBackButton();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { user } = useAuth();
  const [wallet, setWallet] = useState(user?.linked_wallet ?? "");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    const value = wallet.trim();
    if (!value) {
      showToast("Please enter a wallet address", { type: "error" });
      return;
    }
    setSaving(true);
    try {
      await apiFetch<ProfileResponse>("/auth/me/wallet", {
        method: "POST",
        body: JSON.stringify({ linked_wallet: value }),
      });
      showToast("Wallet saved", { type: "success" });
      navigate(-1);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Error", { type: "error" });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Text type="title2" weight="bold">
        Payout Wallet
      </Text>

      <Group header="TON Address">
        <div className="px-4 py-3">
          <Input
            placeholder="EQ..."
            type="text"
            value={wallet}
            onChange={(v) => setWallet(v)}
          />
        </div>
      </Group>

      <div className="flex flex-col gap-2">
        <Button text="Save" type="primary" loading={saving} onClick={save} />
        <Button text="Back" type="secondary" onClick={() => navigate(-1)} />
      </div>
    </div>
  );
}
