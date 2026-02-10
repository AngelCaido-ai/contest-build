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

  const copyAddress = () => {
    if (escrow?.deposit_address) {
      navigator.clipboard.writeText(escrow.deposit_address);
      showToast("Адрес скопирован", { type: "success" });
    }
  };

  const sendTransaction = async () => {
    if (!escrow) return;
    if (!wallet) {
      showToast("Подключите кошелек", { type: "error" });
      return;
    }
    setSending(true);
    try {
      const amountNano = Math.round((escrow.expected_amount ?? 0) * 1e9).toString();
      await tonConnectUI.sendTransaction({
        validUntil: Math.floor(Date.now() / 1000) + 600,
        messages: [
          {
            address: escrow.deposit_address,
            amount: amountNano,
            ...(escrow.deposit_comment ? { payload: escrow.deposit_comment } : {}),
          },
        ],
      });
      showToast("Транзакция отправлена", { type: "success" });
      navigate(`/deals/${id}`);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Ошибка транзакции", { type: "error" });
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
        <Text type="body" color="danger">{error ?? "Не удалось создать депозит"}</Text>
        <Button text="Назад" type="secondary" onClick={() => navigate(-1)} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Text type="title2" weight="bold">
        Оплата сделки #{id}
      </Text>

      {escrow.confirmed_at ? (
        <Group>
          <div className="flex flex-col items-center gap-3 py-6">
            <span className="text-4xl">✅</span>
            <Text type="title3" weight="bold" color="accent">
              Оплата подтверждена
            </Text>
            <Button
              text="К сделке"
              type="primary"
              onClick={() => navigate(`/deals/${id}`)}
            />
          </div>
        </Group>
      ) : (
        <>
          <Group header="Депозитный адрес">
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

          <Group header="Сумма">
            <GroupItem
              text="К оплате"
              after={
                <Text type="body" weight="bold">
                  {escrow.expected_amount != null
                    ? `${escrow.expected_amount} TON`
                    : "Не указана"}
                </Text>
              }
            />
            {escrow.deposit_comment && (
              <GroupItem
                text="Комментарий"
                after={<Text type="body">{escrow.deposit_comment}</Text>}
              />
            )}
          </Group>

          <div className="flex flex-col gap-2 pt-2">
            {!wallet && (
              <Button
                text="Подключить кошелек"
                type="secondary"
                onClick={() => tonConnectUI.openModal()}
              />
            )}
            <Button
              text={wallet ? "Оплатить через TonConnect" : "Оплатить"}
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
