import { useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTonConnectUI, useTonWallet } from "@tonconnect/ui-react";
import { QRCodeSVG } from "qrcode.react";
import {
  Text,
  Button,
  Group,
  GroupItem,
  Spinner,
  useToast,
} from "@telegram-tools/ui-kit";
import { apiFetch } from "../api/client";
import { useApi } from "../hooks/useApi";
import { useBackButton } from "../hooks/useBackButton";
import type { EscrowPayment } from "../types";

export function PaymentPage() {
  useBackButton();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [tonConnectUI] = useTonConnectUI();
  const wallet = useTonWallet();

  const [sending, setSending] = useState(false);

  const fetcher = useCallback(
    () =>
      apiFetch<EscrowPayment>(`/escrow/deals/${id}/deposit`, { method: "POST", body: JSON.stringify({}) }),
    [id],
  );
  const { data: escrow, loading, error } = useApi(fetcher, [id]);

  const buildCommentPayload = async (comment: string) => {
    const { Buffer } = await import("buffer");
    (globalThis as any).Buffer ??= Buffer;

    const tonCore = await import("@ton/core");
    return tonCore
      .beginCell()
      .storeUint(0, 32)
      .storeStringTail(comment)
      .endCell()
      .toBoc()
      .toString("base64");
  };

  const copyAddress = () => {
    if (escrow?.deposit_address) {
      navigator.clipboard.writeText(escrow.deposit_address);
      showToast("Address copied", { type: "success" });
    }
  };

  const sendTransaction = async () => {
    if (!escrow) return;
    if (!wallet) {
      showToast("Please connect a wallet", { type: "error" });
      return;
    }
    setSending(true);
    try {
      const amountNano = Math.round((escrow.expected_amount ?? 0) * 1e9).toString();
      const payload = escrow.deposit_comment ? await buildCommentPayload(escrow.deposit_comment) : undefined;
      await tonConnectUI.sendTransaction({
        validUntil: Math.floor(Date.now() / 1000) + 600,
        messages: [
          {
            address: escrow.deposit_address,
            amount: amountNano,
            ...(payload ? { payload } : {}),
          },
        ],
      });
      showToast("Transaction sent", { type: "success" });
      navigate(`/deals/${id}`);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Transaction error", { type: "error" });
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner size="32px" />
      </div>
    );
  }

  if (error || !escrow) {
    return (
      <div className="flex flex-col items-center gap-3 py-12">
        <Text type="body" color="danger">{error ?? "Failed to create deposit"}</Text>
        <Button text="Back" type="secondary" onClick={() => navigate(-1)} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Text type="title2" weight="bold">
        Deal Payment #{id}
      </Text>

      {escrow.confirmed_at ? (
        <Group>
          <div className="flex flex-col items-center gap-3 py-6">
            <span className="text-4xl">✅</span>
            <Text type="title3" weight="bold" color="accent">
              Payment confirmed
            </Text>
            <Button
              text="Go to Deal"
              type="primary"
              onClick={() => navigate(`/deals/${id}`)}
            />
          </div>
        </Group>
      ) : (
        <>
          <Group header="Deposit Address">
            <div className="flex flex-col items-center gap-4 py-4">
              <QRCodeSVG
                value={`ton://transfer/${escrow.deposit_address}${escrow.expected_amount ? `?amount=${Math.round(escrow.expected_amount * 1e9)}` : ""}`}
                size={200}
                bgColor="transparent"
                fgColor="currentColor"
              />
              <button
                onClick={copyAddress}
                className="max-w-full break-all px-4 text-center"
              >
                <Text type="caption1" color="accent">
                  {escrow.deposit_address}
                </Text>
              </button>
            </div>
          </Group>

          <Group header="Amount">
            <GroupItem
              text="To pay"
              after={
                <Text type="body" weight="bold">
                  {escrow.expected_amount != null
                    ? `${escrow.expected_amount} TON`
                    : "Not specified"}
                </Text>
              }
            />
            {escrow.deposit_comment && (
              <GroupItem
                text="Comment"
                after={<Text type="body">{escrow.deposit_comment}</Text>}
              />
            )}
          </Group>

          <div className="flex flex-col gap-2 pt-2">
            {!wallet && (
              <Button
                text="Connect Wallet"
                type="secondary"
                onClick={() => tonConnectUI.openModal()}
              />
            )}
            <Button
              text={wallet ? "Pay via TonConnect" : "Pay"}
              type="primary"
              loading={sending}
              disabled={!wallet}
              onClick={sendTransaction}
            />
          </div>
        </>
      )}
    </div>
  );
}
