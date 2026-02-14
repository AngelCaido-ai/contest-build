import base64
import os
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.models
from app.core.config import settings
from app.db.base import Base
from app.models.channel import Channel
from app.models.deal import Deal
from app.models.enums import DealStatus
from app.models.user import User
from app.services import escrow_service, ton_escrow
from app.services.deal_service import set_status


class EscrowServiceTests(unittest.TestCase):
    def setUp(self):
        self._prev_escrow_key = settings.escrow_secret_key
        self._prev_prefix = settings.ton_deposit_comment_prefix
        settings.escrow_secret_key = base64.urlsafe_b64encode(b"0" * 32).decode()
        settings.ton_deposit_comment_prefix = "deal"
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def tearDown(self):
        settings.escrow_secret_key = self._prev_escrow_key
        settings.ton_deposit_comment_prefix = self._prev_prefix

    def _create_deal(self, db, status=DealStatus.TERMS_LOCKED):
        advertiser = User(tg_user_id=1001, roles=[], linked_wallet="adv_wallet")
        owner = User(tg_user_id=2002, roles=[], linked_wallet="owner_wallet")
        db.add_all([advertiser, owner])
        db.commit()
        channel = Channel(
            tg_chat_id=555,
            owner_user_id=owner.id,
            bot_admin_status=True,
        )
        db.add(channel)
        db.commit()
        deal = Deal(
            advertiser_id=advertiser.id,
            channel_id=channel.id,
            price=1.0,
            status=status,
        )
        db.add(deal)
        db.commit()
        db.refresh(deal)
        return deal, advertiser, owner, channel

    @patch("app.services.ton_escrow.create_deposit_wallet")
    def test_create_deposit_sets_fields(self, mock_create):
        mock_create.return_value = ("EQD", "alpha beta gamma")
        db = self.Session()
        deal, _, _, _ = self._create_deal(db)
        payment = escrow_service.create_deposit(db, deal, 1.23)
        self.assertEqual(payment.deposit_address, "EQD")
        self.assertNotEqual(payment.deposit_key, "alpha beta gamma")
        self.assertEqual(ton_escrow.decrypt_deposit_key(payment.deposit_key), "alpha beta gamma")
        self.assertEqual(payment.deposit_comment, f"deal:{deal.id}")
        self.assertEqual(deal.status, DealStatus.AWAITING_PAYMENT)
        db.close()

    def test_confirm_payment_idempotent(self):
        db = self.Session()
        deal, _, _, _ = self._create_deal(db)
        payment = escrow_service.create_deposit(db, deal, 1.0)
        escrow_service.confirm_payment(db, deal, payment, "tx1")
        payment = db.get(type(payment), payment.id)
        self.assertEqual(payment.tx_hash, "tx1")
        escrow_service.confirm_payment(db, deal, payment, "tx2")
        payment = db.get(type(payment), payment.id)
        self.assertEqual(payment.tx_hash, "tx1")
        self.assertEqual(deal.status, DealStatus.FUNDED)
        db.close()

    @patch("app.services.ton_escrow.find_incoming_tx")
    def test_scan_incoming_payments_updates(self, mock_find):
        mock_find.return_value = "tx_found"
        db = self.Session()
        deal, _, _, _ = self._create_deal(db)
        payment = escrow_service.create_deposit(db, deal, 1.0)
        processed = escrow_service.scan_incoming_payments(db)
        updated = db.get(type(payment), payment.id)
        self.assertEqual(processed, 1)
        self.assertEqual(updated.tx_hash, "tx_found")
        self.assertEqual(deal.status, DealStatus.FUNDED)
        mock_find.assert_called_once()
        db.close()

    @patch("app.services.ton_escrow.send_payout")
    def test_release_payment_uses_owner_wallet(self, mock_send):
        mock_send.return_value = "payout_tx"
        db = self.Session()
        deal, _, _, _ = self._create_deal(db)
        payment = escrow_service.create_deposit(db, deal, 1.0)
        payment.tx_hash = "funded"
        set_status(deal, DealStatus.FUNDED)
        set_status(deal, DealStatus.CREATIVE_REVIEW)
        set_status(deal, DealStatus.APPROVED)
        set_status(deal, DealStatus.VERIFYING)
        db.commit()
        updated = escrow_service.release_payment(db, deal, None)
        self.assertEqual(updated.release_tx_hash, "payout_tx")
        self.assertEqual(updated.payout_address, "owner_wallet")
        self.assertEqual(deal.status, DealStatus.RELEASED)
        db.close()

    @patch("app.services.ton_escrow.send_refund")
    def test_refund_payment_uses_advertiser_wallet(self, mock_send):
        mock_send.return_value = "refund_tx"
        db = self.Session()
        deal, advertiser, _, _ = self._create_deal(db)
        payment = escrow_service.create_deposit(db, deal, 1.0)
        payment.tx_hash = "funded"
        set_status(deal, DealStatus.FUNDED)
        set_status(deal, DealStatus.CREATIVE_REVIEW)
        set_status(deal, DealStatus.APPROVED)
        set_status(deal, DealStatus.VERIFYING)
        db.commit()
        updated = escrow_service.refund_payment(db, deal, None, "reason")
        self.assertEqual(updated.refund_tx_hash, "refund_tx")
        self.assertEqual(updated.refund_address, advertiser.linked_wallet)
        self.assertEqual(deal.status, DealStatus.REFUNDED)
        db.close()

    def test_release_payment_missing_payout_address(self):
        db = self.Session()
        deal, _, owner, channel = self._create_deal(db)
        owner.linked_wallet = None
        channel.owner_user_id = owner.id
        db.commit()
        payment = escrow_service.create_deposit(db, deal, 1.0)
        payment.tx_hash = "funded"
        set_status(deal, DealStatus.FUNDED)
        set_status(deal, DealStatus.CREATIVE_REVIEW)
        set_status(deal, DealStatus.APPROVED)
        set_status(deal, DealStatus.VERIFYING)
        db.commit()
        with self.assertRaises(ValueError):
            escrow_service.release_payment(db, deal, None)
        db.close()

    def test_refund_payment_missing_refund_address(self):
        db = self.Session()
        deal, advertiser, _, _ = self._create_deal(db)
        advertiser.linked_wallet = None
        db.commit()
        payment = escrow_service.create_deposit(db, deal, 1.0)
        payment.tx_hash = "funded"
        set_status(deal, DealStatus.FUNDED)
        set_status(deal, DealStatus.CREATIVE_REVIEW)
        set_status(deal, DealStatus.APPROVED)
        set_status(deal, DealStatus.VERIFYING)
        db.commit()
        with self.assertRaises(ValueError):
            escrow_service.refund_payment(db, deal, None, None)
        db.close()


class ConcurrentReleaseTests(unittest.TestCase):
    def setUp(self):
        self._prev_escrow_key = settings.escrow_secret_key
        self._prev_prefix = settings.ton_deposit_comment_prefix
        settings.escrow_secret_key = base64.urlsafe_b64encode(b"0" * 32).decode()
        settings.ton_deposit_comment_prefix = "deal"
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        db_url = f"sqlite:///{self._tmp.name}"
        self.engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)

    def tearDown(self):
        settings.escrow_secret_key = self._prev_escrow_key
        settings.ton_deposit_comment_prefix = self._prev_prefix
        self.engine.dispose()
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass

    def _create_funded_deal(self, db):
        advertiser = User(tg_user_id=3001, roles=[], linked_wallet="adv_wallet")
        owner = User(tg_user_id=4002, roles=[], linked_wallet="owner_wallet")
        db.add_all([advertiser, owner])
        db.commit()
        channel = Channel(
            tg_chat_id=777,
            owner_user_id=owner.id,
            bot_admin_status=True,
        )
        db.add(channel)
        db.commit()
        deal = Deal(
            advertiser_id=advertiser.id,
            channel_id=channel.id,
            price=1.0,
            status=DealStatus.TERMS_LOCKED,
        )
        db.add(deal)
        db.commit()
        db.refresh(deal)
        payment = escrow_service.create_deposit(db, deal, 1.0)
        payment.tx_hash = "funded"
        set_status(deal, DealStatus.FUNDED)
        set_status(deal, DealStatus.CREATIVE_REVIEW)
        set_status(deal, DealStatus.APPROVED)
        set_status(deal, DealStatus.VERIFYING)
        db.commit()
        db.refresh(payment)
        return deal.id

    @patch("app.services.ton_escrow.send_payout")
    def test_concurrent_release_single_payout(self, mock_send):
        mock_send.return_value = "payout_tx"
        db_setup = self.Session()
        deal_id = self._create_funded_deal(db_setup)
        db_setup.close()

        release_lock = threading.Lock()
        results = [None, None]
        errors = [None, None]

        def worker(idx):
            db = self.Session()
            try:
                deal = db.get(Deal, deal_id)
                with release_lock:
                    result = escrow_service.release_payment(db, deal, None)
                results[idx] = result.release_tx_hash
            except Exception as exc:
                errors[idx] = exc
            finally:
                db.close()

        t1 = threading.Thread(target=worker, args=(0,))
        t2 = threading.Thread(target=worker, args=(1,))
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        for i, err in enumerate(errors):
            if err is not None:
                raise AssertionError(f"Thread {i} raised: {err}")

        self.assertEqual(mock_send.call_count, 1, "send_payout should be called exactly once")
        self.assertEqual(results[0], "payout_tx")
        self.assertEqual(results[1], "payout_tx")
