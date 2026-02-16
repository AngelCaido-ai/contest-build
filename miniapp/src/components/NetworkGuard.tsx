import { useEffect } from "react";
import { useTonConnectUI, useTonWallet, CHAIN } from "@tonconnect/ui-react";
import { useToast } from "@telegram-tools/ui-kit";

const REQUIRED_CHAIN =
  import.meta.env.VITE_TON_NETWORK === "mainnet" ? CHAIN.MAINNET : CHAIN.TESTNET;

const NETWORK_LABEL = REQUIRED_CHAIN === CHAIN.TESTNET ? "testnet" : "mainnet";

export function NetworkGuard() {
  const [tonConnectUI] = useTonConnectUI();
  const wallet = useTonWallet();
  const { showToast } = useToast();

  useEffect(() => {
    if (wallet && wallet.account.chain !== REQUIRED_CHAIN) {
      tonConnectUI.disconnect();
      showToast(
        `Wrong network! Please switch your wallet to ${NETWORK_LABEL} and reconnect.`,
        { type: "error" },
      );
    }
  }, [wallet, tonConnectUI, showToast]);

  return null;
}
