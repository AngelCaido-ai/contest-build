import base64
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pytoniq import Address as PytoniqAddress
from pytoniq import StateInit as PytoniqStateInit
from pytoniq.contract.wallets.wallet import mnemonic_to_private_key
from pytoniq.contract.wallets.wallet_v5 import WALLET_V5_R1_CODE, WalletV5R1, WalletV5WalletID
from pytoniq_core.boc import Builder, begin_cell
from pytoniq_core.crypto.signature import sign_message
from tonsdk.contract.wallet import Wallets, WalletVersionEnum
from tonsdk.utils import Address, bytes_to_b64str, to_nano

from app.core.config import settings
from app.utils.ton_address import validate_ton_address

logger = logging.getLogger(__name__)


def _toncenter_root_url() -> str:
    network = (settings.ton_network or "").lower()
    if network == "testnet":
        base = "https://testnet.toncenter.com"
    elif network == "mainnet":
        base = settings.ton_api_url
    else:
        base = settings.ton_api_url
    for suffix in ("/api/v2", "/api/v3"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    return base.rstrip("/")


def _toncenter_base_url_v2() -> str:
    return f"{_toncenter_root_url()}/api/v2"


def _toncenter_base_url_v3() -> str:
    return f"{_toncenter_root_url()}/api/v3"


def _is_testnet() -> bool:
    network = (settings.ton_network or "").lower()
    if network == "testnet":
        return True
    if network == "mainnet":
        return False
    return "testnet" in settings.ton_api_url.lower()


def _toncenter_request(
    method: str,
    path: str,
    params: dict | None = None,
    payload: dict | None = None,
    base_url: str | None = None,
) -> Any:
    base_url = base_url or _toncenter_base_url_v2()
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    params = params or {}
    headers: dict[str, str] = {}
    if settings.ton_api_key:
        params.setdefault("api_key", settings.ton_api_key)
        headers["X-API-Key"] = settings.ton_api_key
    response = requests.request(
        method,
        url,
        params=params,
        json=payload,
        headers=headers or None,
        timeout=settings.ton_api_timeout_seconds,
    )
    response.raise_for_status()
    try:
        data = response.json()
    except ValueError as exc:
        body = (response.text or "").strip()
        if len(body) > 500:
            body = body[:500] + "..."
        raise ValueError(f"toncenter_non_json_response status={response.status_code} body={body!r}") from exc
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, str) and error:
            raise ValueError(error)
        if data.get("ok") is False:
            raise ValueError(data.get("error") or "ton_api_error")
        if "result" in data:
            return data["result"]
    return data


def _toncenter_get(path: str, params: dict) -> Any:
    return _toncenter_request("GET", path, params=params, base_url=_toncenter_base_url_v2())


def _toncenter_post(path: str, payload: dict) -> Any:
    return _toncenter_request("POST", path, payload=payload, base_url=_toncenter_base_url_v2())


def _toncenter_get_v3(path: str, params: dict) -> Any:
    return _toncenter_request("GET", path, params=params, base_url=_toncenter_base_url_v3())


def _toncenter_post_v3(path: str, payload: dict) -> Any:
    return _toncenter_request("POST", path, payload=payload, base_url=_toncenter_base_url_v3())


def _toncenter_wallet_state_v3(address: str) -> dict | None:
    params = {"address": [address]}
    result = _toncenter_get_v3("walletStates", params)
    if isinstance(result, dict):
        wallets = result.get("wallets")
        if isinstance(wallets, list) and wallets:
            return wallets[0]
    return None


def _toncenter_transactions_v3(address: str, limit: int) -> list[dict] | None:
    params = {"account": [address], "limit": limit, "sort": "desc"}
    result = _toncenter_get_v3("transactions", params)
    if isinstance(result, dict):
        txs = result.get("transactions")
        if isinstance(txs, list):
            return txs
    if isinstance(result, list):
        return result
    return None


def _toncenter_transactions(address: str, limit: int) -> list[dict] | None:
    try:
        txs = _toncenter_transactions_v3(address, limit)
        if txs is not None:
            return txs
    except Exception:
        pass
    result = _toncenter_get("getTransactions", {"address": address, "limit": limit})
    if isinstance(result, list):
        return result
    return None

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
            raise ValueError("deposit_key_too_short")
        nonce = raw[:12]
        encrypted = raw[12:]
        aesgcm = AESGCM(_escrow_key())
        return aesgcm.decrypt(nonce, encrypted, None).decode()
    except Exception as exc:
        raise ValueError(f"deposit_key_decrypt_failed: {exc}") from exc


def build_deposit_comment(deal_id: int) -> str:
    prefix = settings.ton_deposit_comment_prefix or "deal"
    return f"{prefix}:{deal_id}"


def _normalize_address(value: str | None) -> str:
    if not value:
        return ""
    return validate_ton_address(value)


def _extract_comment(in_msg: dict) -> str | None:
    comment = in_msg.get("comment")
    if isinstance(comment, str) and comment:
        return comment
    message = in_msg.get("message")
    if isinstance(message, str) and message:
        return message
    message_content = in_msg.get("message_content")
    if isinstance(message_content, dict):
        decoded = message_content.get("decoded")
        if isinstance(decoded, dict):
            for key in ("comment", "text", "message"):
                value = decoded.get(key)
                if isinstance(value, str) and value:
                    return value
                if isinstance(value, dict):
                    nested = value.get("text") or value.get("value") or value.get("comment")
                    if isinstance(nested, str) and nested:
                        return nested
        if isinstance(decoded, str) and decoded:
            return decoded
        body = message_content.get("body")
        if isinstance(body, str) and body:
            return body
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
    if _is_wallet_v5_version():
        return _wallet_from_key_v5(mnemonics)
    version = _resolve_wallet_version(mnemonics)
    _, _, _, wallet = Wallets.from_mnemonics(mnemonics, version, 0)
    return wallet


def _is_wallet_v5_version() -> bool:
    value = (settings.ton_wallet_version or "").strip().lower()
    return value in ("v5r1", "v5beta", "v5", "w5")


def _wallet_v5_network_global_id() -> int:
    return -3 if _is_testnet() else -239


@dataclass
class _WalletV5:
    address: Address
    address_raw: PytoniqAddress
    private_key: bytes
    wallet_id: int


def _wallet_from_key_v5(mnemonics: list[str]) -> _WalletV5:
    public_key, private_key = mnemonic_to_private_key(mnemonics)
    wallet_id = settings.ton_wallet_id
    if wallet_id is None:
        wallet_id = WalletV5WalletID(
            network_global_id=_wallet_v5_network_global_id(),
            workchain=0,
            subwallet_number=settings.ton_wallet_subwallet or 0,
        ).pack()
        data = WalletV5R1.create_data_cell(
            public_key,
            wc=0,
            wallet_id=wallet_id,
            is_signature_allowed=True,
        )
    else:
        data = WalletV5R1.create_data_cell(
            public_key,
            wc=0,
            wallet_id=wallet_id,
            is_signature_allowed=True,
        )
    state_init = PytoniqStateInit(code=WALLET_V5_R1_CODE, data=data)
    address_raw = PytoniqAddress((0, state_init.serialize().hash))
    address = Address(
        address_raw.to_str(
            is_user_friendly=True,
            is_url_safe=True,
            is_bounceable=True,
            is_test_only=_is_testnet(),
        )
    )
    return _WalletV5(address=address, address_raw=address_raw, private_key=private_key, wallet_id=wallet_id)


def _wallet_version_candidates() -> list[tuple[str, WalletVersionEnum]]:
    candidates: list[tuple[str, WalletVersionEnum]] = []
    for name in (
        "v1r1",
        "v1r2",
        "v1r3",
        "v2r1",
        "v2r2",
        "v3r1",
        "v3r2",
        "v4r1",
        "v4r2",
        "v5r1",
        "v5beta",
    ):
        enum_value = getattr(WalletVersionEnum, name, None)
        if enum_value is not None:
            candidates.append((name, enum_value))
    return candidates


def _resolve_wallet_version(mnemonics: list[str]) -> WalletVersionEnum:
    requested = (settings.ton_wallet_version or "").strip().lower()
    candidates = _wallet_version_candidates()
    if requested:
        for name, enum_value in candidates:
            if name == requested:
                return enum_value
        raise ValueError("ton_wallet_version_invalid")
    detected: WalletVersionEnum | None = None
    best_score = -1
    for name, enum_value in candidates:
        _, _, _, wallet = Wallets.from_mnemonics(mnemonics, enum_value, 0)
        address = wallet.address.to_string(True, True, True, is_test_only=_is_testnet())
        score = 0
        try:
            state = _toncenter_wallet_state_v3(address)
            if isinstance(state, dict):
                if state.get("is_wallet"):
                    score += 2
                if int(state.get("seqno") or 0) > 0:
                    score += 2
                if int(state.get("balance") or 0) > 0:
                    score += 3
                if str(state.get("status") or "") == "active":
                    score += 1
        except Exception:
            score = 0
        if score == 0:
            try:
                info = _toncenter_get("getWalletInformation", {"address": address})
                if isinstance(info, dict):
                    wallet_type = str(info.get("wallet_type") or "").lower()
                    if name in wallet_type:
                        score += 2
                    if int(info.get("seqno") or 0) > 0:
                        score += 2
                    if int(info.get("balance") or 0) > 0:
                        score += 3
            except Exception:
                score = 0
        if score > best_score:
            best_score = score
            detected = enum_value
    if detected is None:
        return WalletVersionEnum.v4r2
    return detected


def _wallet_seqno(address: str) -> int:
    seqno = None
    try:
        state = _toncenter_wallet_state_v3(address)
        if isinstance(state, dict):
            seqno = state.get("seqno")
    except Exception:
        seqno = None
    if seqno is None:
        result = _toncenter_get("getWalletInformation", {"address": address})
        if isinstance(result, dict):
            seqno = result.get("seqno")
    if seqno is None:
        return 0
    try:
        return int(seqno)
    except (TypeError, ValueError):
        return 0


def _wallet_balance_nano(address: str) -> int:
    balance = None
    try:
        state = _toncenter_wallet_state_v3(address)
        if isinstance(state, dict):
            balance = state.get("balance")
    except Exception:
        balance = None
    if balance is None:
        info = _toncenter_get("getAddressInformation", {"address": address})
        if isinstance(info, dict):
            balance = info.get("balance")
    if balance is None:
        return 0
    try:
        return int(balance)
    except (TypeError, ValueError):
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


def _extract_message_hash(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if isinstance(value, dict):
        nested = value.get("result")
        if nested is not None and nested is not value:
            nested_hash = _extract_message_hash(nested)
            if nested_hash:
                return nested_hash
        for key in (
            "message_hash",
            "message_hash_norm",
            "transactionHash",
            "hash",
            "inMsgHash",
            "in_msg_hash",
        ):
            raw = value.get(key)
            if raw:
                return str(raw)
    return None


def _is_transient_send_error(exc: Exception) -> bool:
    text = str(exc).lower()
    if any(token in text for token in ("timeout", "timed out", "temporarily", "try again", "rate limit", "too many")):
        return True
    if any(code in text for code in (" 429", " 500", " 502", " 503", " 504")):
        return True
    return False


def _send_boc(boc: str) -> str:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            result = _toncenter_post_v3("message", {"boc": boc})
            message_hash = _extract_message_hash(result)
            if message_hash:
                return message_hash
            last_error = ValueError(f"ton_v3_send_empty_response result={result!r}")
        except Exception as exc:
            last_error = exc
        if attempt < 2 and last_error is not None and _is_transient_send_error(last_error):
            time.sleep(0.4 * (attempt + 1))
            continue
        break
    v2_error: Exception | None = None
    try:
        result = _toncenter_post("sendBocReturnHash", {"boc": boc})
        message_hash = _extract_message_hash(result)
        if message_hash:
            return message_hash
        v2_error = ValueError(f"ton_v2_send_empty_response result={result!r}")
    except Exception as exc:
        v2_error = exc
        try:
            result = _toncenter_post("sendBoc", {"boc": boc})
            message_hash = _extract_message_hash(result)
            if message_hash:
                return message_hash
            v2_error = ValueError(f"ton_v2_send_empty_response result={result!r}")
        except Exception as exc2:
            v2_error = exc2
    if v2_error is not None and last_error is not None:
        raise ValueError(f"ton_send_failed v3_error={last_error} v2_error={v2_error}") from v2_error
    if last_error is not None:
        raise ValueError(f"ton_send_failed v3_error={last_error}") from last_error
    raise ValueError("ton_send_failed")


def derive_deposit_key(deal_id: int) -> str:
    if not settings.ton_hot_wallet:
        raise ValueError("ton_hot_wallet_missing")
    return settings.ton_hot_wallet


def create_deposit_wallet(deal_id: int) -> tuple[str, str]:
    try:
        mnemonics, _, _, wallet = Wallets.create(WalletVersionEnum.v4r2, 0)
        deposit_key = " ".join(mnemonics)
        deposit_address = wallet.address.to_string(True, True, True, is_test_only=_is_testnet())
        logger.info("create_deposit_wallet: deal_id=%s address=%s", deal_id, deposit_address)
        return deposit_address, deposit_key
    except Exception:
        logger.exception("create_deposit_wallet: error deal_id=%s", deal_id)
        raise


def find_incoming_tx(
    deposit_address: str,
    expected_amount: float | None,
    expected_comment: str | None,
) -> str | None:
    logger.info("find_incoming_tx: address=%s expected_amount=%s", deposit_address, expected_amount)
    txs = _toncenter_transactions(deposit_address, 20)
    if not isinstance(txs, list):
        logger.warning("find_incoming_tx: no transactions for address=%s", deposit_address)
        return None
    expected_nano = _amount_to_nano(expected_amount) if expected_amount is not None else None
    for tx in txs:
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
    logger.info("send_payout: to=%s amount=%s", payout_address, amount)
    if _is_wallet_v5_version():
        wallet = _wallet_from_key(deposit_key)
        wallet_address = wallet.address.to_string(True, True, True, is_test_only=_is_testnet())
        seqno = _wallet_seqno(wallet_address)
        amount_nano = _resolve_send_amount_nano(wallet_address, amount)
        boc = _create_transfer_boc_v5(wallet, payout_address, amount_nano, seqno)
        return _send_boc(boc)
    wallet = _wallet_from_key(deposit_key)
    wallet_address = wallet.address.to_string(True, True, True, is_test_only=_is_testnet())
    seqno = _wallet_seqno(wallet_address)
    amount_nano = _resolve_send_amount_nano(wallet_address, amount)
    query = wallet.create_transfer_message(payout_address, amount_nano, seqno)
    boc = bytes_to_b64str(query["message"].to_boc(False))
    return _send_boc(boc)


def send_refund(deposit_key: str, refund_address: str, amount: float | None) -> str:
    logger.info("send_refund: to=%s amount=%s", refund_address, amount)
    if _is_wallet_v5_version():
        wallet = _wallet_from_key(deposit_key)
        wallet_address = wallet.address.to_string(True, True, True, is_test_only=_is_testnet())
        seqno = _wallet_seqno(wallet_address)
        amount_nano = _resolve_send_amount_nano(wallet_address, amount)
        boc = _create_transfer_boc_v5(wallet, refund_address, amount_nano, seqno)
        return _send_boc(boc)
    wallet = _wallet_from_key(deposit_key)
    wallet_address = wallet.address.to_string(True, True, True, is_test_only=_is_testnet())
    seqno = _wallet_seqno(wallet_address)
    amount_nano = _resolve_send_amount_nano(wallet_address, amount)
    query = wallet.create_transfer_message(refund_address, amount_nano, seqno)
    boc = bytes_to_b64str(query["message"].to_boc(False))
    return _send_boc(boc)


def send_sweep(deposit_key: str, destination: str) -> str | None:
    logger.info("send_sweep: to=%s", destination)
    min_balance_ton = settings.sweep_min_balance_ton or 0
    min_balance_nano = int(to_nano(str(min_balance_ton), "ton"))
    if _is_wallet_v5_version():
        wallet = _wallet_from_key(deposit_key)
        wallet_address = wallet.address.to_string(True, True, True, is_test_only=_is_testnet())
        balance_nano = _wallet_balance_nano(wallet_address)
        if balance_nano <= min_balance_nano:
            logger.info("send_sweep: skip low balance address=%s balance=%s", wallet_address, balance_nano)
            return None
        seqno = _wallet_seqno(wallet_address)
        boc = _create_transfer_boc_v5(wallet, destination, 0, seqno, send_mode=128)
        return _send_boc(boc)
    wallet = _wallet_from_key(deposit_key)
    wallet_address = wallet.address.to_string(True, True, True, is_test_only=_is_testnet())
    balance_nano = _wallet_balance_nano(wallet_address)
    if balance_nano <= min_balance_nano:
        logger.info("send_sweep: skip low balance address=%s balance=%s", wallet_address, balance_nano)
        return None
    seqno = _wallet_seqno(wallet_address)
    query = wallet.create_transfer_message(destination, 0, seqno, send_mode=128)
    boc = bytes_to_b64str(query["message"].to_boc(False))
    return _send_boc(boc)


def _create_transfer_boc_v5(wallet: _WalletV5, destination: str, amount_nano: int, seqno: int, send_mode: int = 3) -> str:
    dest = PytoniqAddress(destination)
    msg = WalletV5R1.create_wallet_internal_message(destination=dest, value=amount_nano, send_mode=send_mode)
    op_code = 0x7369676e
    signing_message = begin_cell().store_uint(op_code, 32)
    signing_message.store_uint(wallet.wallet_id, 32)
    if seqno == 0:
        signing_message.store_uint(2**32 - 1, 32)
    else:
        signing_message.store_uint(int(time.time()) + 60, 32)
    signing_message.store_uint(seqno, 32)
    signing_message.store_cell(WalletV5R1.pack_actions([msg]))
    signing_message = signing_message.end_cell()
    signature = sign_message(signing_message.hash, wallet.private_key)
    transfer = Builder().store_cell(signing_message).store_bytes(signature).end_cell()
    ext = WalletV5R1.create_external_msg(dest=wallet.address_raw, body=transfer)
    boc = ext.serialize().to_boc()
    return base64.b64encode(boc).decode()
