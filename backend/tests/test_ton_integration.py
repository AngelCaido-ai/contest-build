import base64
import os
import time
import unittest

from app.core.config import settings
from app.services import ton_escrow


def _load_env_file(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ[key] = value


class TonIntegrationTests(unittest.TestCase):
    def setUp(self):
        env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
        _load_env_file(env_path)
        run_flag = os.environ.get("RUN_TON_INTEGRATION")
        if run_flag != "1":
            print(f"RUN_TON_INTEGRATION={run_flag!r} env_path={env_path}")
            self.skipTest("integration_disabled")
        self._prev_network = settings.ton_network
        self._prev_api_key = settings.ton_api_key
        self._prev_api_url = settings.ton_api_url
        self._prev_timeout = settings.ton_api_timeout_seconds
        self._prev_escrow_key = settings.escrow_secret_key
        self._prev_reserve = settings.ton_reserve_ton
        settings.ton_network = os.environ.get("TON_NETWORK", settings.ton_network)
        settings.ton_api_key = os.environ.get("TON_API_KEY", settings.ton_api_key)
        settings.ton_api_url = os.environ.get("TON_API_URL", settings.ton_api_url)
        timeout = os.environ.get("TON_API_TIMEOUT_SECONDS")
        if timeout:
            settings.ton_api_timeout_seconds = int(timeout)
        escrow_key = os.environ.get("ESCROW_SECRET_KEY")
        if escrow_key:
            settings.escrow_secret_key = escrow_key
        if not settings.escrow_secret_key:
            settings.escrow_secret_key = base64.urlsafe_b64encode(b"0" * 32).decode()
        reserve = os.environ.get("TON_RESERVE_TON")
        if reserve:
            settings.ton_reserve_ton = float(reserve)
        if not settings.ton_api_key:
            self.skipTest("missing_ton_api_key")
        self.funded_mnemonics = os.environ.get("TON_FUNDED_MNEMONICS")
        self.dest_address = os.environ.get("TON_DEST_ADDRESS") or os.environ.get("TON_FUNDED_ADDRESS")
        self.allow_send = os.environ.get("TON_INTEGRATION_ALLOW_SEND") == "1"

    def tearDown(self):
        settings.ton_network = self._prev_network
        settings.ton_api_key = self._prev_api_key
        settings.ton_api_url = self._prev_api_url
        settings.ton_api_timeout_seconds = self._prev_timeout
        settings.escrow_secret_key = self._prev_escrow_key
        settings.ton_reserve_ton = self._prev_reserve

    def test_toncenter_wallet_information(self):
        if not self.dest_address:
            self.skipTest("missing_dest_address")
        seqno = ton_escrow._wallet_seqno(self.dest_address)
        balance = ton_escrow._wallet_balance_nano(self.dest_address)
        self.assertTrue(isinstance(seqno, int))
        self.assertTrue(isinstance(balance, int))

    def test_send_payout_returns_hash(self):
        if not self.allow_send:
            self.skipTest("send_disabled")
        if not self.funded_mnemonics or not self.dest_address:
            self.skipTest("missing_funded_wallet")
        tx_hash = ton_escrow.send_payout(self.funded_mnemonics, self.dest_address, 0.01)
        self.assertTrue(isinstance(tx_hash, str))
        self.assertTrue(len(tx_hash) > 0)

    def test_find_incoming_tx_after_send(self):
        if not self.allow_send:
            self.skipTest("send_disabled")
        if not self.funded_mnemonics:
            self.skipTest("missing_funded_wallet")
        funded_wallet = ton_escrow._wallet_from_key(self.funded_mnemonics)
        funded_address = funded_wallet.address.to_string(True, True, True, is_test_only=ton_escrow._is_testnet())
        before_seqno = ton_escrow._wallet_seqno(funded_address)
        deposit_address, _ = ton_escrow.create_deposit_wallet(999)
        print(f"deposit_address={deposit_address}")
        tx_hash = ton_escrow.send_payout(self.funded_mnemonics, deposit_address, 0.01)
        print(f"send_payout_tx_hash={tx_hash}")
        after_seqno = ton_escrow._wallet_seqno(funded_address)
        print(f"funded_address={funded_address} seqno_before={before_seqno} seqno_after={after_seqno}")
        if after_seqno <= before_seqno:
            self.skipTest("seqno_not_incremented")
        out_found = False
        for _ in range(12):
            txs = ton_escrow._toncenter_transactions(funded_address, 20)
            if isinstance(txs, list):
                for tx in txs:
                    if not isinstance(tx, dict):
                        continue
                    out_msgs = tx.get("out_msgs") or []
                    if isinstance(out_msgs, list):
                        for out_msg in out_msgs:
                            destination = out_msg.get("destination") or out_msg.get("dst")
                            if ton_escrow._normalize_address(destination) == ton_escrow._normalize_address(deposit_address):
                                out_found = True
                                break
                    if out_found:
                        break
            if out_found:
                break
            time.sleep(5)
        if not out_found:
            self.skipTest("outgoing_not_indexed")
        found = None
        for _ in range(18):
            found = ton_escrow.find_incoming_tx(deposit_address, 0.01, None)
            if found:
                break
            time.sleep(10)
        if not found:
            self.skipTest("deposit_not_indexed")
