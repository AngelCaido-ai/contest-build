import base64
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models
from app.core.config import settings
from app.db.base import Base
from app.models.channel import Channel
from app.models.deal import Deal
from app.models.enums import DealStatus
from app.models.user import User
from app.services import escrow_service, ton_escrow


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
        deal, _, _, _ = self._create_deal(db, status=DealStatus.AWAITING_PAYMENT)
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
        deal, _, _, _ = self._create_deal(db, status=DealStatus.AWAITING_PAYMENT)
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
        deal, _, _, _ = self._create_deal(db, status=DealStatus.FUNDED)
        payment = escrow_service.create_deposit(db, deal, 1.0)
        payment.tx_hash = "funded"
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
        deal, advertiser, _, _ = self._create_deal(db, status=DealStatus.FUNDED)
        payment = escrow_service.create_deposit(db, deal, 1.0)
        payment.tx_hash = "funded"
        db.commit()
        updated = escrow_service.refund_payment(db, deal, None, "reason")
        self.assertEqual(updated.refund_tx_hash, "refund_tx")
        self.assertEqual(updated.refund_address, advertiser.linked_wallet)
        self.assertEqual(deal.status, DealStatus.REFUNDED)
        db.close()

    def test_release_payment_missing_payout_address(self):
        db = self.Session()
        deal, _, owner, channel = self._create_deal(db, status=DealStatus.FUNDED)
        owner.linked_wallet = None
        channel.owner_user_id = owner.id
        db.commit()
        payment = escrow_service.create_deposit(db, deal, 1.0)
        payment.tx_hash = "funded"
        db.commit()
        with self.assertRaises(ValueError):
            escrow_service.release_payment(db, deal, None)
        db.close()

    def test_refund_payment_missing_refund_address(self):
        db = self.Session()
        deal, advertiser, _, _ = self._create_deal(db, status=DealStatus.FUNDED)
        advertiser.linked_wallet = None
        db.commit()
        payment = escrow_service.create_deposit(db, deal, 1.0)
        payment.tx_hash = "funded"
        db.commit()
        with self.assertRaises(ValueError):
            escrow_service.refund_payment(db, deal, None, None)
        db.close()
