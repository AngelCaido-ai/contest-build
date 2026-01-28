import base64
import unittest
from unittest.mock import patch

from app.core.config import settings
from app.services import ton_escrow


class TonEscrowTests(unittest.TestCase):
    def setUp(self):
        self._prev_escrow_key = settings.escrow_secret_key
        self._prev_reserve = settings.ton_reserve_ton
        settings.escrow_secret_key = base64.urlsafe_b64encode(b"0" * 32).decode()
        settings.ton_reserve_ton = 0.1

    def tearDown(self):
        settings.escrow_secret_key = self._prev_escrow_key
        settings.ton_reserve_ton = self._prev_reserve

    def test_encrypt_decrypt_roundtrip(self):
        plain = (
            "one two three four five six seven eight nine ten eleven twelve "
            "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty "
            "twentyone twentytwo twentythree twentyfour"
        )
        encrypted = ton_escrow.encrypt_deposit_key(plain)
        self.assertNotEqual(plain, encrypted)
        decrypted = ton_escrow.decrypt_deposit_key(encrypted)
        self.assertEqual(plain, decrypted)

    def test_decrypt_plain_fallback(self):
        plain = "alpha beta gamma"
        decrypted = ton_escrow.decrypt_deposit_key(plain)
        self.assertEqual(plain, decrypted)

    def test_extract_comment_from_message(self):
        in_msg = {"message": "deal:1"}
        self.assertEqual(ton_escrow._extract_comment(in_msg), "deal:1")

    def test_extract_comment_from_msg_data(self):
        in_msg = {"msg_data": {"text": "deal:2"}}
        self.assertEqual(ton_escrow._extract_comment(in_msg), "deal:2")
        in_msg = {"msg_data": {"body": "deal:3"}}
        self.assertEqual(ton_escrow._extract_comment(in_msg), "deal:3")

    def test_extract_comment_empty(self):
        self.assertIsNone(ton_escrow._extract_comment({}))
        self.assertIsNone(ton_escrow._extract_comment({"message": ""}))

    def test_ensure_escrow_secret_key_generates(self):
        settings.escrow_secret_key = None
        ton_escrow.ensure_escrow_secret_key()
        self.assertIsNotNone(settings.escrow_secret_key)
        key_bytes = ton_escrow._decode_escrow_key(settings.escrow_secret_key)
        self.assertEqual(len(key_bytes), 32)

    def test_ensure_escrow_secret_key_invalid_raises(self):
        settings.escrow_secret_key = "bad"
        with self.assertRaises(ValueError):
            ton_escrow.ensure_escrow_secret_key()

    @patch("app.services.ton_escrow._toncenter_get")
    def test_find_incoming_tx_strict(self, mock_get):
        deposit_address = "EQD123"
        comment = "deal:10"
        tx = {
            "in_msg": {"value": "1000", "destination": deposit_address, "message": comment},
            "transaction_id": {"hash": "abc", "lt": "123"},
        }
        mock_get.return_value = [tx]
        tx_id = ton_escrow.find_incoming_tx(deposit_address, 0.000001, comment)
        self.assertEqual(tx_id, "abc:123")
        tx_id_bad_comment = ton_escrow.find_incoming_tx(deposit_address, 0.000001, "deal:11")
        self.assertIsNone(tx_id_bad_comment)

    @patch("app.services.ton_escrow._toncenter_get")
    def test_find_incoming_tx_address_mismatch(self, mock_get):
        deposit_address = "EQD123"
        tx = {
            "in_msg": {"value": "1000", "destination": "EQX999", "message": "deal:10"},
            "transaction_id": {"hash": "abc", "lt": "123"},
        }
        mock_get.return_value = [tx]
        tx_id = ton_escrow.find_incoming_tx(deposit_address, 0.000001, "deal:10")
        self.assertIsNone(tx_id)

    @patch("app.services.ton_escrow._toncenter_get")
    def test_find_incoming_tx_amount_too_small(self, mock_get):
        deposit_address = "EQD123"
        tx = {
            "in_msg": {"value": "1", "destination": deposit_address, "message": "deal:10"},
            "transaction_id": {"hash": "abc", "lt": "123"},
        }
        mock_get.return_value = [tx]
        tx_id = ton_escrow.find_incoming_tx(deposit_address, 1.0, "deal:10")
        self.assertIsNone(tx_id)

    @patch("app.services.ton_escrow._toncenter_get")
    def test_find_incoming_tx_no_comment_required(self, mock_get):
        deposit_address = "EQD123"
        tx = {
            "in_msg": {"value": "1000", "destination": deposit_address},
            "transaction_id": {"hash": "abc", "lt": "123"},
        }
        mock_get.return_value = [tx]
        tx_id = ton_escrow.find_incoming_tx(deposit_address, 0.000001, None)
        self.assertEqual(tx_id, "abc:123")

    @patch("app.services.ton_escrow._wallet_balance_nano")
    def test_resolve_send_amount(self, mock_balance):
        mock_balance.return_value = 1_000_000_000
        amount = ton_escrow._resolve_send_amount_nano("addr", None)
        self.assertEqual(amount, 900_000_000)
        with self.assertRaises(ValueError):
            ton_escrow._resolve_send_amount_nano("addr", 0.95)
