from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.deal import Deal
from app.models.escrow_payment import EscrowPayment
from app.models.enums import DealStatus
from app.models.user import User
from app.models.channel import Channel
from app.services.deal_service import log_event, set_status
from app.services import ton_escrow


def create_deposit(db: Session, deal: Deal, expected_amount: float | None) -> EscrowPayment:
    reserve = settings.ton_reserve_ton or 0
    deal_price = deal.price or 0
    min_amount = deal_price + reserve
    if expected_amount is None or expected_amount < min_amount:
        expected_amount = min_amount
    deposit_address, deposit_key = ton_escrow.create_deposit_wallet(deal.id)
    deposit_key = ton_escrow.encrypt_deposit_key(deposit_key)
    deposit_comment = ton_escrow.build_deposit_comment(deal.id)
    payment = EscrowPayment(
        deal_id=deal.id,
        deposit_address=deposit_address,
        deposit_key=deposit_key,
        deposit_comment=deposit_comment,
        expected_amount=expected_amount,
    )
    db.add(payment)
    set_status(deal, DealStatus.AWAITING_PAYMENT)
    log_event(
        db,
        deal.id,
        "ESCROW_CREATED",
        {"deposit_address": deposit_address, "deposit_comment": deposit_comment},
    )
    db.commit()
    db.refresh(payment)
    return payment


def confirm_payment(db: Session, deal: Deal, payment: EscrowPayment, tx_hash: str) -> EscrowPayment:
    if payment.tx_hash:
        return payment
    payment.tx_hash = tx_hash
    payment.confirmed_at = datetime.utcnow()
    set_status(deal, DealStatus.FUNDED)
    log_event(db, deal.id, "ESCROW_FUNDED", {"tx_hash": tx_hash})
    db.commit()
    db.refresh(payment)
    return payment


def scan_incoming_payments(db: Session) -> int:
    payments = (
        db.query(EscrowPayment)
        .filter(EscrowPayment.tx_hash.is_(None))
        .all()
    )
    processed = 0
    for payment in payments:
        deal = db.get(Deal, payment.deal_id)
        if not deal or deal.status != DealStatus.AWAITING_PAYMENT:
            continue
        tx_hash = ton_escrow.find_incoming_tx(
            payment.deposit_address,
            payment.expected_amount,
            payment.deposit_comment,
        )
        if not tx_hash:
            continue
        confirm_payment(db, deal, payment, tx_hash)
        processed += 1
    return processed


def release_payment(db: Session, deal: Deal, payout_address: str | None) -> EscrowPayment:
    payment = db.query(EscrowPayment).filter(EscrowPayment.deal_id == deal.id).first()
    if not payment or not payment.tx_hash:
        raise ValueError("payment_not_funded")
    if payment.release_tx_hash:
        return payment
    if not payout_address:
        channel = db.get(Channel, deal.channel_id)
        owner = db.get(User, channel.owner_user_id) if channel else None
        payout_address = owner.linked_wallet if owner else None
    if not payout_address:
        raise ValueError("payout_address_missing")
    if payment.deposit_key:
        deposit_key = ton_escrow.decrypt_deposit_key(payment.deposit_key)
    else:
        deposit_key = ton_escrow.derive_deposit_key(deal.id)
    tx_hash = ton_escrow.send_payout(deposit_key, payout_address, deal.price)
    payment.payout_address = payout_address
    payment.release_tx_hash = tx_hash
    payment.released_at = datetime.utcnow()
    set_status(deal, DealStatus.RELEASED)
    log_event(db, deal.id, "ESCROW_RELEASED", {"tx_hash": tx_hash})
    db.commit()
    db.refresh(payment)
    return payment


def refund_payment(db: Session, deal: Deal, refund_address: str | None, reason: str | None) -> EscrowPayment:
    payment = db.query(EscrowPayment).filter(EscrowPayment.deal_id == deal.id).first()
    if not payment or not payment.tx_hash:
        raise ValueError("payment_not_funded")
    if payment.refund_tx_hash:
        return payment
    if not refund_address:
        advertiser = db.get(User, deal.advertiser_id)
        refund_address = advertiser.linked_wallet if advertiser else None
    if not refund_address:
        raise ValueError("refund_address_missing")
    if payment.deposit_key:
        deposit_key = ton_escrow.decrypt_deposit_key(payment.deposit_key)
    else:
        deposit_key = ton_escrow.derive_deposit_key(deal.id)
    tx_hash = ton_escrow.send_refund(deposit_key, refund_address, deal.price)
    payment.refund_address = refund_address
    payment.refund_tx_hash = tx_hash
    payment.refunded_at = datetime.utcnow()
    set_status(deal, DealStatus.REFUNDED)
    payload = {"tx_hash": tx_hash}
    if reason:
        payload["reason"] = reason
    log_event(db, deal.id, "ESCROW_REFUNDED", payload)
    db.commit()
    db.refresh(payment)
    return payment
