import base64
import os
from typing import Any

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from tonsdk.contract.wallet import Wallets, WalletVersionEnum
from tonsdk.utils import bytes_to_b64str, to_nano

from app.core.config import settings


def _toncenter_base_url() -> str:
    network = (settings.ton_network or "").lower()
    if network == "testnet":
        return "https://testnet.toncenter.com/api/v2"
    if network == "mainnet":
        return settings.ton_api_url
    return settings.ton_api_url


def _is_testnet() -> bool:
    network = (settings.ton_network or "").lower()
    if network == "testnet":
        return True
    if network == "mainnet":
        return False
    return "testnet" in settings.ton_api_url.lower()


def _toncenter_request(method: str, path: str, params: dict | None = None, payload: dict | None = None) -> Any:
    base_url = _toncenter_base_url()
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    params = params or {}
    if settings.ton_api_key:
        params["api_key"] = settings.ton_api_key
    response = requests.request(method, url, params=params, json=payload, timeout=settings.ton_api_timeout_seconds)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict) and data.get("ok") is False:
        raise ValueError(data.get("error") or "ton_api_error")
    if isinstance(data, dict) and "result" in data:
        return data["result"]
    return data


def _toncenter_get(path: str, params: dict) -> Any:
    return _toncenter_request("GET", path, params=params)


def _toncenter_post(path: str, payload: dict) -> Any:
    return _toncenter_request("POST", path, payload=payload)


def _b64decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode())


def _decode_escrow_key(value: str) -> bytes:
    key = _b64decode(value)
    if len(key) not in (16, 24, 32):
        raise ValueError("escrow_key_invalid")
    return key


def _escrow_key() -> bytes:
    if not settings.escrow_secret_key:
        raise ValueError("escrow_key_missing")
    return _decode_escrow_key(settings.escrow_secret_key)


def ensure_escrow_secret_key() -> None:
    if not settings.escrow_secret_key:
        key_bytes = os.urandom(32)
        settings.escrow_secret_key = base64.urlsafe_b64encode(key_bytes).decode()
        return
    _decode_escrow_key(settings.escrow_secret_key)


def encrypt_deposit_key(deposit_key: str) -> str:
    aesgcm = AESGCM(_escrow_key())
    nonce = os.urandom(12)
    encrypted = aesgcm.encrypt(nonce, deposit_key.encode(), None)
    return base64.urlsafe_b64encode(nonce + encrypted).decode()


def decrypt_deposit_key(value: str) -> str:
    try:
        raw = _b64decode(value)
        if len(raw) <= 12:
            raise ValueError("token_short")
        nonce = raw[:12]
        encrypted = raw[12:]
        aesgcm = AESGCM(_escrow_key())
        return aesgcm.decrypt(nonce, encrypted, None).decode()
    except Exception:
        return value


def build_deposit_comment(deal_id: int) -> str:
    prefix = settings.ton_deposit_comment_prefix or "deal"
    return f"{prefix}:{deal_id}"


def _normalize_address(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().lower()


def _extract_comment(in_msg: dict) -> str | None:
    message = in_msg.get("message")
    if isinstance(message, str) and message:
        return message
    msg_data = in_msg.get("msg_data")
    if isinstance(msg_data, dict):
        text = msg_data.get("text")
        if isinstance(text, str) and text:
            return text
        body = msg_data.get("body")
        if isinstance(body, str) and body:
            return body
    return None


def _amount_to_nano(amount: float | None) -> int:
    if amount is None:
        raise ValueError("amount_missing")
    return int(to_nano(str(amount), "ton"))


def _wallet_from_key(deposit_key: str):
    mnemonics = deposit_key.split()
    _, _, _, wallet = Wallets.from_mnemonics(mnemonics, WalletVersionEnum.v4r2, 0)
    return wallet


def _wallet_seqno(address: str) -> int:
    result = _toncenter_get("getWalletInformation", {"address": address})
    if isinstance(result, dict):
        seqno = result.get("seqno")
        if seqno is None:
            return 0
        try:
            return int(seqno)
        except (TypeError, ValueError):
            return 0
    return 0


def _wallet_balance_nano(address: str) -> int:
    info = _toncenter_get("getAddressInformation", {"address": address})
    if isinstance(info, dict):
        balance = info.get("balance")
        if balance is not None:
            try:
                return int(balance)
            except (TypeError, ValueError):
                return 0
    return 0


def _reserve_nano() -> int:
    return _amount_to_nano(settings.ton_reserve_ton)


def _resolve_send_amount_nano(address: str, amount: float | None) -> int:
    reserve = _reserve_nano()
    balance = _wallet_balance_nano(address)
    available = balance - reserve
    if available <= 0:
        raise ValueError("insufficient_balance")
    if amount is None:
        return available
    amount_nano = _amount_to_nano(amount)
    if amount_nano > available:
        raise ValueError("insufficient_balance")
    return amount_nano


def _extract_tx_id(tx: dict) -> str | None:
    transaction_id = tx.get("transaction_id") or {}
    hash_value = transaction_id.get("hash") or tx.get("hash")
    lt_value = transaction_id.get("lt") or tx.get("lt")
    if hash_value and lt_value:
        return f"{hash_value}:{lt_value}"
    if hash_value:
        return str(hash_value)
    return None


def _send_boc(boc: str) -> str:
    try:
        result = _toncenter_post("sendBocReturnHash", {"boc": boc})
    except Exception:
        result = _toncenter_post("sendBoc", {"boc": boc})
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return str(result.get("result") or result.get("transactionHash") or result.get("hash") or "")
    return str(result)


def derive_deposit_key(deal_id: int) -> str:
    if not settings.ton_hot_wallet:
        raise ValueError("ton_hot_wallet_missing")
    return settings.ton_hot_wallet


def create_deposit_wallet(deal_id: int) -> tuple[str, str]:
    mnemonics, _, _, wallet = Wallets.create(WalletVersionEnum.v4r2, 0)
    deposit_key = " ".join(mnemonics)
    deposit_address = wallet.address.to_string(True, True, True, is_test_only=_is_testnet())
    return deposit_address, deposit_key


def find_incoming_tx(
    deposit_address: str,
    expected_amount: float | None,
    expected_comment: str | None,
) -> str | None:
    params = {"address": deposit_address, "limit": 20}
    result = _toncenter_get("getTransactions", params)
    if not isinstance(result, list):
        return None
    expected_nano = _amount_to_nano(expected_amount) if expected_amount is not None else None
    for tx in result:
        if not isinstance(tx, dict):
            continue
        in_msg = tx.get("in_msg") or {}
        destination = in_msg.get("destination") or in_msg.get("dst")
        if destination and _normalize_address(destination) != _normalize_address(deposit_address):
            continue
        value_raw = in_msg.get("value")
        try:
            value = int(value_raw)
        except (TypeError, ValueError):
            value = 0
        if value <= 0:
            continue
        if expected_nano is not None and value < expected_nano:
            continue
        if expected_comment:
            comment = _extract_comment(in_msg)
            if comment != expected_comment:
                continue
        tx_id = _extract_tx_id(tx)
        if tx_id:
            return tx_id
    return None


def send_payout(deposit_key: str, payout_address: str, amount: float | None) -> str:
    wallet = _wallet_from_key(deposit_key)
    wallet_address = wallet.address.to_string(True, True, True, is_test_only=_is_testnet())
    seqno = _wallet_seqno(wallet_address)
    amount_nano = _resolve_send_amount_nano(wallet_address, amount)
    query = wallet.create_transfer_message(payout_address, amount_nano, seqno)
    boc = bytes_to_b64str(query["message"].to_boc(False))
    return _send_boc(boc)


def send_refund(deposit_key: str, refund_address: str, amount: float | None) -> str:
    wallet = _wallet_from_key(deposit_key)
    wallet_address = wallet.address.to_string(True, True, True, is_test_only=_is_testnet())
    seqno = _wallet_seqno(wallet_address)
    amount_nano = _resolve_send_amount_nano(wallet_address, amount)
    query = wallet.create_transfer_message(refund_address, amount_nano, seqno)
    boc = bytes_to_b64str(query["message"].to_boc(False))
    return _send_boc(boc)
