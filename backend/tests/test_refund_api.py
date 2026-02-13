import base64
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.models  # noqa: F401
from app.api.deps import get_db
from app.core.config import settings
from app.db.base import Base
from app.main import app
from app.models.deal import Deal
from app.models.escrow_payment import EscrowPayment
from app.services.escrow_service import confirm_payment, refund_payment, release_payment
from app.services import ton_escrow

VALID_TON_ADDRESS = "EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAM9c"


class RefundApiTests(unittest.TestCase):
    def setUp(self):
        self._prev_bot_secret = settings.bot_secret
        self._prev_escrow_key = settings.escrow_secret_key
        self._prev_jwt_secret = settings.jwt_secret
        self._prev_network = settings.ton_network
        self._prev_api_key = settings.ton_api_key
        self._prev_api_url = settings.ton_api_url
        self._prev_timeout = settings.ton_api_timeout_seconds
        self._prev_reserve = settings.ton_reserve_ton
        self._prev_wallet_version = settings.ton_wallet_version
        self._prev_wallet_id = settings.ton_wallet_id
        self._prev_wallet_subwallet = settings.ton_wallet_subwallet
        self._prev_limiter_enabled = app.state.limiter.enabled
        settings.bot_secret = "test-bot-secret"
        settings.jwt_secret = "test-jwt-secret"
        settings.escrow_secret_key = base64.urlsafe_b64encode(b"0" * 32).decode()
        app.state.limiter.enabled = False

        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides = {}
        settings.bot_secret = self._prev_bot_secret
        settings.escrow_secret_key = self._prev_escrow_key
        settings.jwt_secret = self._prev_jwt_secret
        settings.ton_network = self._prev_network
        settings.ton_api_key = self._prev_api_key
        settings.ton_api_url = self._prev_api_url
        settings.ton_api_timeout_seconds = self._prev_timeout
        settings.ton_reserve_ton = self._prev_reserve
        settings.ton_wallet_version = self._prev_wallet_version
        settings.ton_wallet_id = self._prev_wallet_id
        settings.ton_wallet_subwallet = self._prev_wallet_subwallet
        app.state.limiter.enabled = self._prev_limiter_enabled

    def _confirm_via_service(self, deal_id: int, tx_hash: str) -> None:
        db = self.Session()
        try:
            deal = db.get(Deal, deal_id)
            payment = db.query(EscrowPayment).filter(EscrowPayment.deal_id == deal_id).first()
            confirm_payment(db, deal, payment, tx_hash)
        finally:
            db.close()

    def _create_funded_deal(self, brief: str = "API validation test") -> tuple[dict[str, str], int]:
        headers_bot = {"X-Bot-Secret": settings.bot_secret}
        auth_resp = self.client.post(
            "/auth/bot",
            json={"tg_user_id": 1001, "roles": ["advertiser"]},
            headers=headers_bot,
        )
        self.assertEqual(auth_resp.status_code, 200)
        token = auth_resp.json()["token"]
        headers_user = {"Authorization": f"Bearer {token}"}

        channel_resp = self.client.post(
            "/bot/channels",
            json={
                "owner_tg_user_id": 2002,
                "tg_chat_id": -1003830865844,
                "username": "test_channel",
                "title": "Test Channel",
                "bot_admin_status": True,
            },
            headers=headers_bot,
        )
        self.assertEqual(channel_resp.status_code, 200)
        channel_id = channel_resp.json()["channel_id"]

        request_resp = self.client.post(
            "/bot/requests",
            json={"advertiser_tg_user_id": 1001, "budget": 0.05, "brief": brief},
            headers=headers_bot,
        )
        self.assertEqual(request_resp.status_code, 200)
        request_id = request_resp.json()["id"]

        deal_resp = self.client.post(
            "/bot/deals",
            json={
                "owner_tg_user_id": 2002,
                "request_id": request_id,
                "channel_id": channel_id,
                "price": 0.05,
                "format": "post",
            },
            headers=headers_bot,
        )
        self.assertEqual(deal_resp.status_code, 200)
        deal_id = deal_resp.json()["id"]

        terms_resp = self.client.post(
            f"/bot/deals/{deal_id}/terms",
            json={"price": 0.05, "format": "post", "actor_tg_user_id": 2002},
            headers=headers_bot,
        )
        self.assertEqual(terms_resp.status_code, 200)

        deposit_resp = self.client.post(
            f"/escrow/deals/{deal_id}/deposit",
            json={"expected_amount": 0.05},
            headers=headers_user,
        )
        self.assertEqual(deposit_resp.status_code, 200)

        self._confirm_via_service(deal_id, "tx_test")
        return headers_bot, deal_id

    def test_refund_flow_without_miniapp(self):
        headers_bot = {"X-Bot-Secret": settings.bot_secret}
        auth_resp = self.client.post(
            "/auth/bot",
            json={"tg_user_id": 1001, "roles": ["advertiser"]},
            headers=headers_bot,
        )
        self.assertEqual(auth_resp.status_code, 200)
        token = auth_resp.json()["token"]
        headers_user = {"Authorization": f"Bearer {token}"}

        channel_resp = self.client.post(
            "/bot/channels",
            json={
                "owner_tg_user_id": 2002,
                "tg_chat_id": -1003830865844,
                "username": "test_channel",
                "title": "Test Channel",
                "bot_admin_status": True,
            },
            headers=headers_bot,
        )
        self.assertEqual(channel_resp.status_code, 200)
        channel_id = channel_resp.json()["channel_id"]

        request_resp = self.client.post(
            "/bot/requests",
            json={"advertiser_tg_user_id": 1001, "budget": 0.05, "brief": "API refund test"},
            headers=headers_bot,
        )
        self.assertEqual(request_resp.status_code, 200)
        request_id = request_resp.json()["id"]

        deal_resp = self.client.post(
            "/bot/deals",
            json={
                "owner_tg_user_id": 2002,
                "request_id": request_id,
                "channel_id": channel_id,
                "price": 0.05,
                "format": "post",
            },
            headers=headers_bot,
        )
        self.assertEqual(deal_resp.status_code, 200)
        deal_id = deal_resp.json()["id"]

        terms_resp = self.client.post(
            f"/bot/deals/{deal_id}/terms",
            json={"price": 0.05, "format": "post", "actor_tg_user_id": 2002},
            headers=headers_bot,
        )
        self.assertEqual(terms_resp.status_code, 200)

        deposit_resp = self.client.post(
            f"/escrow/deals/{deal_id}/deposit",
            json={"expected_amount": 0.05},
            headers=headers_user,
        )
        self.assertEqual(deposit_resp.status_code, 200)

        self._confirm_via_service(deal_id, "tx_test")

        db = self.Session()
        try:
            deal = db.get(Deal, deal_id)
            self.assertEqual(deal.status.value, "FUNDED")
            with patch("app.services.ton_escrow.send_refund", return_value="refund_tx") as mock_send:
                payment = refund_payment(db, deal, VALID_TON_ADDRESS, "api_test")
            self.assertEqual(payment.refund_tx_hash, "refund_tx")
            self.assertEqual(payment.refund_address, VALID_TON_ADDRESS)
            self.assertIsNotNone(payment.refunded_at)
            self.assertEqual(mock_send.call_count, 1)
            _, called_address, called_amount = mock_send.call_args.args
            self.assertEqual(called_address, VALID_TON_ADDRESS)
            self.assertAlmostEqual(float(called_amount), 0.05, places=8)
        finally:
            db.close()

        deal_status_resp = self.client.get(f"/bot/deals/{deal_id}", headers=headers_bot)
        self.assertEqual(deal_status_resp.status_code, 200)
        self.assertEqual(deal_status_resp.json()["status"], "REFUNDED")

    def test_release_flow_without_miniapp(self):
        headers_bot = {"X-Bot-Secret": settings.bot_secret}
        auth_resp = self.client.post(
            "/auth/bot",
            json={"tg_user_id": 1001, "roles": ["advertiser"]},
            headers=headers_bot,
        )
        self.assertEqual(auth_resp.status_code, 200)
        token = auth_resp.json()["token"]
        headers_user = {"Authorization": f"Bearer {token}"}

        channel_resp = self.client.post(
            "/bot/channels",
            json={
                "owner_tg_user_id": 2002,
                "tg_chat_id": -1003830865844,
                "username": "test_channel",
                "title": "Test Channel",
                "bot_admin_status": True,
            },
            headers=headers_bot,
        )
        self.assertEqual(channel_resp.status_code, 200)
        channel_id = channel_resp.json()["channel_id"]

        request_resp = self.client.post(
            "/bot/requests",
            json={"advertiser_tg_user_id": 1001, "budget": 0.05, "brief": "API release test"},
            headers=headers_bot,
        )
        self.assertEqual(request_resp.status_code, 200)
        request_id = request_resp.json()["id"]

        deal_resp = self.client.post(
            "/bot/deals",
            json={
                "owner_tg_user_id": 2002,
                "request_id": request_id,
                "channel_id": channel_id,
                "price": 0.05,
                "format": "post",
            },
            headers=headers_bot,
        )
        self.assertEqual(deal_resp.status_code, 200)
        deal_id = deal_resp.json()["id"]

        terms_resp = self.client.post(
            f"/bot/deals/{deal_id}/terms",
            json={"price": 0.05, "format": "post", "actor_tg_user_id": 2002},
            headers=headers_bot,
        )
        self.assertEqual(terms_resp.status_code, 200)

        deposit_resp = self.client.post(
            f"/escrow/deals/{deal_id}/deposit",
            json={"expected_amount": 0.05},
            headers=headers_user,
        )
        self.assertEqual(deposit_resp.status_code, 200)

        self._confirm_via_service(deal_id, "tx_test")

        db = self.Session()
        try:
            deal = db.get(Deal, deal_id)
            self.assertEqual(deal.status.value, "FUNDED")
            with patch("app.services.ton_escrow.send_payout", return_value="payout_tx") as mock_send:
                payment = release_payment(db, deal, VALID_TON_ADDRESS)
            self.assertEqual(payment.release_tx_hash, "payout_tx")
            self.assertEqual(payment.payout_address, VALID_TON_ADDRESS)
            self.assertIsNotNone(payment.released_at)
            self.assertEqual(mock_send.call_count, 1)
            _, called_address, called_amount = mock_send.call_args.args
            self.assertEqual(called_address, VALID_TON_ADDRESS)
            self.assertAlmostEqual(float(called_amount), 0.05, places=8)
        finally:
            db.close()

        deal_status_resp = self.client.get(f"/bot/deals/{deal_id}", headers=headers_bot)
        self.assertEqual(deal_status_resp.status_code, 200)
        self.assertEqual(deal_status_resp.json()["status"], "RELEASED")

    def test_refund_flow_testnet(self):
        def _mask(value: str | None, show: int = 4) -> str:
            if not value:
                return "<empty>"
            if len(value) <= show * 2:
                return f"{value[:1]}***"
            return f"{value[:show]}...{value[-show:]}"

        def _log(message: str) -> None:
            print(f"[refund-testnet] {message}")

        def _skip(reason: str) -> None:
            _log(f"SKIP: {reason}")
            self.skipTest(reason)

        def _load_env_file(path: Path) -> None:
            if not path.exists():
                return
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value

        env_path = Path(__file__).resolve().parents[2] / ".env"
        _load_env_file(env_path)

        if os.environ.get("RUN_TON_INTEGRATION") != "1":
            _skip("integration_disabled")
        if os.environ.get("TON_INTEGRATION_ALLOW_SEND") != "1":
            _skip("send_disabled")

        settings.ton_network = os.environ.get("TON_NETWORK", settings.ton_network)
        settings.ton_api_key = os.environ.get("TON_API_KEY", settings.ton_api_key)
        settings.ton_api_url = os.environ.get("TON_API_URL", settings.ton_api_url)
        timeout = os.environ.get("TON_API_TIMEOUT_SECONDS")
        if timeout:
            settings.ton_api_timeout_seconds = int(timeout)
        reserve = os.environ.get("TON_RESERVE_TON")
        if reserve:
            settings.ton_reserve_ton = float(reserve)
        wallet_version = os.environ.get("TON_WALLET_VERSION")
        if wallet_version:
            settings.ton_wallet_version = wallet_version
        wallet_id = os.environ.get("TON_WALLET_ID")
        if wallet_id:
            settings.ton_wallet_id = int(wallet_id)
        wallet_subwallet = os.environ.get("TON_WALLET_SUBWALLET")
        if wallet_subwallet:
            settings.ton_wallet_subwallet = int(wallet_subwallet)

        source_mnemonics = os.environ.get("TON_SOURCE_MNEMONICS") or os.environ.get("TON_FUNDED_MNEMONICS")
        source_address = (
            os.environ.get("TON_SOURCE_ADDRESS")
            or os.environ.get("TON_FUNDED_ADDRESS")
            or os.environ.get("TON_DEST_ADDRESS")
        )
        refund_address = os.environ.get("TON_REFUND_ADDRESS") or os.environ.get("TON_DEST_ADDRESS")
        _log(
            "env: "
            f"network={settings.ton_network} "
            f"api_url={settings.ton_api_url} "
            f"api_key={_mask(settings.ton_api_key)} "
            f"wallet_version={settings.ton_wallet_version or '<auto>'} "
            f"wallet_id={settings.ton_wallet_id} "
            f"subwallet={settings.ton_wallet_subwallet} "
            f"source_mnemonics={'set' if source_mnemonics else '<empty>'} "
            f"source_address={_mask(source_address)} "
            f"refund_address={_mask(refund_address)}"
        )

        if not settings.ton_api_key:
            _skip("missing_ton_api_key")
        if not source_mnemonics:
            _skip("missing_source_mnemonics")
        if not refund_address:
            _skip("missing_refund_address")
        if (settings.ton_network or "").lower() != "testnet" and "testnet" not in (
            settings.ton_api_url or ""
        ).lower():
            _skip("not_testnet")
        if settings.ton_wallet_version and settings.ton_wallet_version.strip().lower() in ("v5r1", "v5beta", "v5", "w5"):
            _skip("deposit_wallet_v4r2_required")

        refund_amount = float(os.environ.get("TON_REFUND_AMOUNT", "0.01"))
        deposit_amount = float(os.environ.get("TON_DEPOSIT_AMOUNT", "0.05"))
        min_required = refund_amount + float(settings.ton_reserve_ton or 0) + 0.001
        _log(
            "amounts: "
            f"deposit={deposit_amount} "
            f"refund={refund_amount} "
            f"reserve={settings.ton_reserve_ton} "
            f"min_required>{min_required:.6f}"
        )
        if deposit_amount <= min_required:
            _skip("deposit_amount_too_small")

        headers_bot = {"X-Bot-Secret": settings.bot_secret}
        auth_resp = self.client.post(
            "/auth/bot",
            json={"tg_user_id": 1001, "roles": ["advertiser"]},
            headers=headers_bot,
        )
        self.assertEqual(auth_resp.status_code, 200)
        token = auth_resp.json()["token"]
        headers_user = {"Authorization": f"Bearer {token}"}

        channel_resp = self.client.post(
            "/bot/channels",
            json={
                "owner_tg_user_id": 2002,
                "tg_chat_id": -1003830865844,
                "username": "test_channel",
                "title": "Test Channel",
                "bot_admin_status": True,
            },
            headers=headers_bot,
        )
        self.assertEqual(channel_resp.status_code, 200)
        channel_id = channel_resp.json()["channel_id"]

        request_resp = self.client.post(
            "/bot/requests",
            json={"advertiser_tg_user_id": 1001, "budget": refund_amount, "brief": "API refund testnet"},
            headers=headers_bot,
        )
        self.assertEqual(request_resp.status_code, 200)
        request_id = request_resp.json()["id"]

        deal_resp = self.client.post(
            "/bot/deals",
            json={
                "owner_tg_user_id": 2002,
                "request_id": request_id,
                "channel_id": channel_id,
                "price": refund_amount,
                "format": "post",
            },
            headers=headers_bot,
        )
        self.assertEqual(deal_resp.status_code, 200)
        deal_id = deal_resp.json()["id"]

        terms_resp = self.client.post(
            f"/bot/deals/{deal_id}/terms",
            json={"price": refund_amount, "format": "post", "actor_tg_user_id": 2002},
            headers=headers_bot,
        )
        self.assertEqual(terms_resp.status_code, 200)

        deposit_resp = self.client.post(
            f"/escrow/deals/{deal_id}/deposit",
            json={"expected_amount": deposit_amount},
            headers=headers_user,
        )
        self.assertEqual(deposit_resp.status_code, 200)
        deposit_address = deposit_resp.json()["deposit_address"]
        _log(f"deposit_address={deposit_address}")

        if source_address and source_mnemonics:
            try:
                derived_wallet = ton_escrow._wallet_from_key(source_mnemonics)
                derived_address = derived_wallet.address.to_string(
                    True, True, True, is_test_only=ton_escrow._is_testnet()
                )
                if ton_escrow._normalize_address(source_address) != ton_escrow._normalize_address(derived_address):
                    _log(
                        "warning: source_address does not match mnemonics "
                        f"source={_mask(source_address)} derived={_mask(derived_address)}"
                    )
            except Exception as exc:
                _log(f"warning: failed to derive source address: {exc}")

        send_address = deposit_address
        try:
            non_bounceable = ton_escrow.Address(deposit_address).to_string(
                True, True, False, is_test_only=ton_escrow._is_testnet()
            )
            if non_bounceable != deposit_address:
                _log(f"deposit_address_non_bounceable={non_bounceable}")
                send_address = non_bounceable
        except Exception as exc:
            _log(f"warning: failed to normalize deposit address: {exc}")

        source_wallet = ton_escrow._wallet_from_key(source_mnemonics)
        source_address_derived = source_wallet.address.to_string(
            True, True, True, is_test_only=ton_escrow._is_testnet()
        )
        source_seqno_before = ton_escrow._wallet_seqno(source_address_derived)
        source_balance_before = ton_escrow._wallet_balance_nano(source_address_derived)
        _log(
            "source_wallet: "
            f"address={_mask(source_address_derived)} "
            f"seqno={source_seqno_before} "
            f"balance_ton={source_balance_before / 1_000_000_000:.6f}"
        )

        deposit_tx = ton_escrow.send_payout(source_mnemonics, send_address, deposit_amount)
        self.assertTrue(isinstance(deposit_tx, str) and deposit_tx)
        _log(f"deposit_tx={deposit_tx}")

        seqno_ok = False
        for attempt in range(10):
            current_seqno = ton_escrow._wallet_seqno(source_address_derived)
            if current_seqno > source_seqno_before:
                seqno_ok = True
                _log(f"source_seqno_incremented={current_seqno}")
                break
            time.sleep(3)
        if not seqno_ok:
            _log("warning: source seqno not incremented")

        target_nano = ton_escrow._amount_to_nano(deposit_amount)
        balance_ok = False
        for attempt in range(24):
            balance_nano = ton_escrow._wallet_balance_nano(deposit_address)
            if balance_nano >= target_nano:
                balance_ok = True
                break
            if attempt % 4 == 0:
                _log(
                    f"waiting_balance attempt={attempt + 1}/24 "
                    f"balance_ton={balance_nano / 1_000_000_000:.6f}"
                )
            time.sleep(5)
        if not balance_ok:
            _log(f"final_balance_ton={balance_nano / 1_000_000_000:.6f}")
            _skip("deposit_not_indexed")

        db = self.Session()
        try:
            deal = db.get(Deal, deal_id)
            payment = db.query(EscrowPayment).filter(EscrowPayment.deal_id == deal_id).first()
            confirm_payment(db, deal, payment, deposit_tx)

            result = refund_payment(db, deal, refund_address, "api_testnet")
            self.assertTrue(result.refund_tx_hash)
            self.assertEqual(
                ton_escrow._normalize_address(result.refund_address),
                ton_escrow._normalize_address(refund_address),
            )
            _log(f"refund_tx={result.refund_tx_hash}")
        finally:
            db.close()

    def test_release_flow_testnet(self):
        def _mask(value: str | None, show: int = 4) -> str:
            if not value:
                return "<empty>"
            if len(value) <= show * 2:
                return f"{value[:1]}***"
            return f"{value[:show]}...{value[-show:]}"

        def _log(message: str) -> None:
            print(f"[release-testnet] {message}")

        def _skip(reason: str) -> None:
            _log(f"SKIP: {reason}")
            self.skipTest(reason)

        def _load_env_file(path: Path) -> None:
            if not path.exists():
                return
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value

        env_path = Path(__file__).resolve().parents[2] / ".env"
        _load_env_file(env_path)

        if os.environ.get("RUN_TON_INTEGRATION") != "1":
            _skip("integration_disabled")
        if os.environ.get("TON_INTEGRATION_ALLOW_SEND") != "1":
            _skip("send_disabled")

        settings.ton_network = os.environ.get("TON_NETWORK", settings.ton_network)
        settings.ton_api_key = os.environ.get("TON_API_KEY", settings.ton_api_key)
        settings.ton_api_url = os.environ.get("TON_API_URL", settings.ton_api_url)
        timeout = os.environ.get("TON_API_TIMEOUT_SECONDS")
        if timeout:
            settings.ton_api_timeout_seconds = int(timeout)
        reserve = os.environ.get("TON_RESERVE_TON")
        if reserve:
            settings.ton_reserve_ton = float(reserve)
        wallet_version = os.environ.get("TON_WALLET_VERSION")
        if wallet_version:
            settings.ton_wallet_version = wallet_version
        wallet_id = os.environ.get("TON_WALLET_ID")
        if wallet_id:
            settings.ton_wallet_id = int(wallet_id)
        wallet_subwallet = os.environ.get("TON_WALLET_SUBWALLET")
        if wallet_subwallet:
            settings.ton_wallet_subwallet = int(wallet_subwallet)

        source_mnemonics = os.environ.get("TON_SOURCE_MNEMONICS") or os.environ.get("TON_FUNDED_MNEMONICS")
        source_address = (
            os.environ.get("TON_SOURCE_ADDRESS")
            or os.environ.get("TON_FUNDED_ADDRESS")
            or os.environ.get("TON_DEST_ADDRESS")
        )
        payout_address = os.environ.get("TON_PAYOUT_ADDRESS") or os.environ.get("TON_DEST_ADDRESS")
        _log(
            "env: "
            f"network={settings.ton_network} "
            f"api_url={settings.ton_api_url} "
            f"api_key={_mask(settings.ton_api_key)} "
            f"wallet_version={settings.ton_wallet_version or '<auto>'} "
            f"wallet_id={settings.ton_wallet_id} "
            f"subwallet={settings.ton_wallet_subwallet} "
            f"source_mnemonics={'set' if source_mnemonics else '<empty>'} "
            f"source_address={_mask(source_address)} "
            f"payout_address={_mask(payout_address)}"
        )

        if not settings.ton_api_key:
            _skip("missing_ton_api_key")
        if not source_mnemonics:
            _skip("missing_source_mnemonics")
        if not payout_address:
            _skip("missing_payout_address")
        if (settings.ton_network or "").lower() != "testnet" and "testnet" not in (
            settings.ton_api_url or ""
        ).lower():
            _skip("not_testnet")
        if settings.ton_wallet_version and settings.ton_wallet_version.strip().lower() in ("v5r1", "v5beta", "v5", "w5"):
            _skip("deposit_wallet_v4r2_required")

        release_amount = float(os.environ.get("TON_RELEASE_AMOUNT") or os.environ.get("TON_REFUND_AMOUNT", "0.01"))
        deposit_amount = float(os.environ.get("TON_DEPOSIT_AMOUNT", "0.05"))
        min_required = release_amount + float(settings.ton_reserve_ton or 0) + 0.001
        _log(
            "amounts: "
            f"deposit={deposit_amount} "
            f"release={release_amount} "
            f"reserve={settings.ton_reserve_ton} "
            f"min_required>{min_required:.6f}"
        )
        if deposit_amount <= min_required:
            _skip("deposit_amount_too_small")

        headers_bot = {"X-Bot-Secret": settings.bot_secret}
        auth_resp = self.client.post(
            "/auth/bot",
            json={"tg_user_id": 1001, "roles": ["advertiser"]},
            headers=headers_bot,
        )
        self.assertEqual(auth_resp.status_code, 200)
        token = auth_resp.json()["token"]
        headers_user = {"Authorization": f"Bearer {token}"}

        channel_resp = self.client.post(
            "/bot/channels",
            json={
                "owner_tg_user_id": 2002,
                "tg_chat_id": -1003830865844,
                "username": "test_channel",
                "title": "Test Channel",
                "bot_admin_status": True,
            },
            headers=headers_bot,
        )
        self.assertEqual(channel_resp.status_code, 200)
        channel_id = channel_resp.json()["channel_id"]

        request_resp = self.client.post(
            "/bot/requests",
            json={"advertiser_tg_user_id": 1001, "budget": release_amount, "brief": "API release testnet"},
            headers=headers_bot,
        )
        self.assertEqual(request_resp.status_code, 200)
        request_id = request_resp.json()["id"]

        deal_resp = self.client.post(
            "/bot/deals",
            json={
                "owner_tg_user_id": 2002,
                "request_id": request_id,
                "channel_id": channel_id,
                "price": release_amount,
                "format": "post",
            },
            headers=headers_bot,
        )
        self.assertEqual(deal_resp.status_code, 200)
        deal_id = deal_resp.json()["id"]

        terms_resp = self.client.post(
            f"/bot/deals/{deal_id}/terms",
            json={"price": release_amount, "format": "post", "actor_tg_user_id": 2002},
            headers=headers_bot,
        )
        self.assertEqual(terms_resp.status_code, 200)

        deposit_resp = self.client.post(
            f"/escrow/deals/{deal_id}/deposit",
            json={"expected_amount": deposit_amount},
            headers=headers_user,
        )
        self.assertEqual(deposit_resp.status_code, 200)
        deposit_address = deposit_resp.json()["deposit_address"]
        _log(f"deposit_address={deposit_address}")

        if source_address and source_mnemonics:
            try:
                derived_wallet = ton_escrow._wallet_from_key(source_mnemonics)
                derived_address = derived_wallet.address.to_string(
                    True, True, True, is_test_only=ton_escrow._is_testnet()
                )
                if ton_escrow._normalize_address(source_address) != ton_escrow._normalize_address(derived_address):
                    _log(
                        "warning: source_address does not match mnemonics "
                        f"source={_mask(source_address)} derived={_mask(derived_address)}"
                    )
            except Exception as exc:
                _log(f"warning: failed to derive source address: {exc}")

        send_address = deposit_address
        try:
            non_bounceable = ton_escrow.Address(deposit_address).to_string(
                True, True, False, is_test_only=ton_escrow._is_testnet()
            )
            if non_bounceable != deposit_address:
                _log(f"deposit_address_non_bounceable={non_bounceable}")
                send_address = non_bounceable
        except Exception as exc:
            _log(f"warning: failed to normalize deposit address: {exc}")

        source_wallet = ton_escrow._wallet_from_key(source_mnemonics)
        source_address_derived = source_wallet.address.to_string(
            True, True, True, is_test_only=ton_escrow._is_testnet()
        )
        source_seqno_before = ton_escrow._wallet_seqno(source_address_derived)
        source_balance_before = ton_escrow._wallet_balance_nano(source_address_derived)
        _log(
            "source_wallet: "
            f"address={_mask(source_address_derived)} "
            f"seqno={source_seqno_before} "
            f"balance_ton={source_balance_before / 1_000_000_000:.6f}"
        )

        deposit_tx = ton_escrow.send_payout(source_mnemonics, send_address, deposit_amount)
        self.assertTrue(isinstance(deposit_tx, str) and deposit_tx)
        _log(f"deposit_tx={deposit_tx}")

        seqno_ok = False
        for attempt in range(10):
            current_seqno = ton_escrow._wallet_seqno(source_address_derived)
            if current_seqno > source_seqno_before:
                seqno_ok = True
                _log(f"source_seqno_incremented={current_seqno}")
                break
            time.sleep(3)
        if not seqno_ok:
            _log("warning: source seqno not incremented")

        target_nano = ton_escrow._amount_to_nano(deposit_amount)
        balance_ok = False
        for attempt in range(24):
            balance_nano = ton_escrow._wallet_balance_nano(deposit_address)
            if balance_nano >= target_nano:
                balance_ok = True
                break
            if attempt % 4 == 0:
                _log(
                    f"waiting_balance attempt={attempt + 1}/24 "
                    f"balance_ton={balance_nano / 1_000_000_000:.6f}"
                )
            time.sleep(5)
        if not balance_ok:
            _log(f"final_balance_ton={balance_nano / 1_000_000_000:.6f}")
            _skip("deposit_not_indexed")

        db = self.Session()
        try:
            deal = db.get(Deal, deal_id)
            payment = db.query(EscrowPayment).filter(EscrowPayment.deal_id == deal_id).first()
            confirm_payment(db, deal, payment, deposit_tx)

            result = release_payment(db, deal, payout_address)
            self.assertTrue(result.release_tx_hash)
            self.assertEqual(
                ton_escrow._normalize_address(result.payout_address),
                ton_escrow._normalize_address(payout_address),
            )
            self.assertIsNotNone(result.released_at)
            _log(f"release_tx={result.release_tx_hash}")
        finally:
            db.close()

        deal_status_resp = self.client.get(f"/bot/deals/{deal_id}", headers=headers_bot)
        self.assertEqual(deal_status_resp.status_code, 200)
        self.assertEqual(deal_status_resp.json()["status"], "RELEASED")
