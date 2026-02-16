import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.deal import Deal
from app.models.escrow_payment import EscrowPayment
from app.models.enums import DealStatus
from app.models.user import User
from app.models.channel import Channel
from app.services.deal_service import InvalidTransitionError, log_event, set_status
from app.services import ton_escrow

logger = logging.getLogger(__name__)


def _lock_row(db: Session, model, *filters):
    q = db.query(model).filter(*filters)
    try:
        if db.bind.dialect.name != "sqlite":
            q = q.with_for_update()
    except Exception:
        q = q.with_for_update()
    return q.first()


def create_deposit(db: Session, deal: Deal, expected_amount: float | None) -> EscrowPayment:
    logger.info("create_deposit: start deal_id=%s expected_amount=%s", deal.id, expected_amount)
    try:
        reserve = Decimal(str(settings.ton_reserve_ton or 0))
        deal_price = deal.price or 0
        if not isinstance(deal_price, Decimal):
            deal_price = Decimal(str(deal_price))
        min_amount = deal_price + reserve
        normalized_expected = expected_amount
        if normalized_expected is not None and not isinstance(normalized_expected, Decimal):
            normalized_expected = Decimal(str(normalized_expected))
        if normalized_expected is None or normalized_expected < min_amount:
            normalized_expected = min_amount
        deposit_address, deposit_key = ton_escrow.create_deposit_wallet(deal.id)
        deposit_key = ton_escrow.encrypt_deposit_key(deposit_key)
        deposit_comment = ton_escrow.build_deposit_comment(deal.id)
        payment = EscrowPayment(
            deal_id=deal.id,
            deposit_address=deposit_address,
            deposit_key=deposit_key,
            deposit_comment=deposit_comment,
            expected_amount=normalized_expected,
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
        logger.info("create_deposit: success deal_id=%s address=%s", deal.id, deposit_address)
        return payment
    except Exception:
        logger.exception("create_deposit: error deal_id=%s", deal.id)
        raise


def confirm_payment(db: Session, deal: Deal, payment: EscrowPayment, tx_hash: str) -> EscrowPayment:
    payment = _lock_row(db, EscrowPayment, EscrowPayment.id == payment.id)
    if payment.tx_hash:
        logger.info("confirm_payment: already confirmed deal_id=%s", deal.id)
        return payment
    try:
        payment.tx_hash = tx_hash
        payment.confirmed_at = datetime.now(timezone.utc)
        set_status(deal, DealStatus.FUNDED)
        log_event(db, deal.id, "ESCROW_FUNDED", {"tx_hash": tx_hash})
        db.commit()
        db.refresh(payment)
        logger.info("confirm_payment: success deal_id=%s tx_hash=%s", deal.id, tx_hash)
        return payment
    except InvalidTransitionError:
        logger.warning("confirm_payment: transition skipped deal_id=%s status=%s", deal.id, deal.status)
        return payment
    except Exception:
        logger.exception("confirm_payment: error deal_id=%s", deal.id)
        raise


def scan_incoming_payments(db: Session) -> int:
    payments = (
        db.query(EscrowPayment)
        .filter(EscrowPayment.tx_hash.is_(None))
        .all()
    )
    logger.info("scan_incoming_payments: checking %d pending payments", len(payments))
    processed = 0
    for payment in payments:
        deal = db.get(Deal, payment.deal_id)
        if not deal or deal.status != DealStatus.AWAITING_PAYMENT:
            continue
        try:
            tx_hash = ton_escrow.find_incoming_tx(
                payment.deposit_address,
                payment.expected_amount,
                payment.deposit_comment,
            )
        except Exception:
            logger.exception("scan_incoming_payments: error checking deal_id=%s address=%s", payment.deal_id, payment.deposit_address)
            continue
        if not tx_hash:
            continue
        payment = _lock_row(db, EscrowPayment, EscrowPayment.id == payment.id)
        deal = _lock_row(db, Deal, Deal.id == payment.deal_id)
        if payment.tx_hash:
            continue
        confirm_payment(db, deal, payment, tx_hash)
        processed += 1
    logger.info("scan_incoming_payments: processed %d payments", processed)
    return processed


def release_payment(db: Session, deal: Deal, payout_address: str | None) -> EscrowPayment:
    logger.info("release_payment: start deal_id=%s", deal.id)
    deal = _lock_row(db, Deal, Deal.id == deal.id)
    payment = _lock_row(db, EscrowPayment, EscrowPayment.deal_id == deal.id)
    if not payment or not payment.tx_hash:
        logger.warning("release_payment: not funded deal_id=%s", deal.id)
        raise ValueError("payment_not_funded")
    if payment.release_tx_hash:
        logger.info("release_payment: already released deal_id=%s", deal.id)
        return payment
    if not payout_address:
        channel = db.get(Channel, deal.channel_id)
        owner = db.get(User, channel.owner_user_id) if channel else None
        payout_address = owner.linked_wallet if owner else None
    if not payout_address:
        logger.warning("release_payment: payout_address_missing deal_id=%s", deal.id)
        raise ValueError("payout_address_missing")
    try:
        if payment.deposit_key:
            deposit_key = ton_escrow.decrypt_deposit_key(payment.deposit_key)
        else:
            deposit_key = ton_escrow.derive_deposit_key(deal.id)
        tx_hash = ton_escrow.send_payout(deposit_key, payout_address, deal.price)
        payment.payout_address = payout_address
        payment.release_tx_hash = tx_hash
        payment.released_at = datetime.now(timezone.utc)
        set_status(deal, DealStatus.RELEASED)
        log_event(db, deal.id, "ESCROW_RELEASED", {"tx_hash": tx_hash})
        db.commit()
        db.refresh(payment)
        logger.info("release_payment: success deal_id=%s tx_hash=%s", deal.id, tx_hash)
        return payment
    except InvalidTransitionError:
        logger.warning("release_payment: transition skipped deal_id=%s status=%s", deal.id, deal.status)
        return payment
    except ValueError:
        raise
    except Exception:
        logger.exception("release_payment: error deal_id=%s", deal.id)
        raise


def refund_payment(db: Session, deal: Deal, refund_address: str | None, reason: str | None) -> EscrowPayment:
    logger.info("refund_payment: start deal_id=%s reason=%s", deal.id, reason)
    deal = _lock_row(db, Deal, Deal.id == deal.id)
    payment = _lock_row(db, EscrowPayment, EscrowPayment.deal_id == deal.id)
    if not payment or not payment.tx_hash:
        logger.warning("refund_payment: not funded deal_id=%s", deal.id)
        raise ValueError("payment_not_funded")
    if payment.refund_tx_hash:
        logger.info("refund_payment: already refunded deal_id=%s", deal.id)
        return payment
    if not refund_address:
        advertiser = db.get(User, deal.advertiser_id)
        refund_address = advertiser.linked_wallet if advertiser else None
    if not refund_address:
        logger.warning("refund_payment: refund_address_missing deal_id=%s", deal.id)
        raise ValueError("refund_address_missing")
    try:
        if payment.deposit_key:
            deposit_key = ton_escrow.decrypt_deposit_key(payment.deposit_key)
        else:
            deposit_key = ton_escrow.derive_deposit_key(deal.id)
        tx_hash = ton_escrow.send_refund(deposit_key, refund_address, deal.price)
        payment.refund_address = refund_address
        payment.refund_tx_hash = tx_hash
        payment.refunded_at = datetime.now(timezone.utc)
        set_status(deal, DealStatus.REFUNDED)
        payload = {"tx_hash": tx_hash}
        if reason:
            payload["reason"] = reason
        log_event(db, deal.id, "ESCROW_REFUNDED", payload)
        db.commit()
        db.refresh(payment)
        logger.info("refund_payment: success deal_id=%s tx_hash=%s", deal.id, tx_hash)
        return payment
    except InvalidTransitionError:
        logger.warning("refund_payment: transition skipped deal_id=%s status=%s", deal.id, deal.status)
        return payment
    except ValueError:
        raise
    except Exception:
        logger.exception("refund_payment: error deal_id=%s", deal.id)
        raise


def sweep_deposit(db: Session, deal: Deal, payment: EscrowPayment) -> EscrowPayment:
    logger.info("sweep_deposit: start deal_id=%s", deal.id)
    deal = _lock_row(db, Deal, Deal.id == deal.id)
    payment = _lock_row(db, EscrowPayment, EscrowPayment.id == payment.id)
    if deal.status not in (DealStatus.RELEASED, DealStatus.REFUNDED):
        logger.warning("sweep_deposit: invalid status deal_id=%s status=%s", deal.id, deal.status)
        raise ValueError("deal_not_completed")
    if payment.sweep_tx_hash:
        logger.info("sweep_deposit: already swept deal_id=%s", deal.id)
        return payment
    advertiser = db.get(User, deal.advertiser_id)
    destination = advertiser.linked_wallet if advertiser else None
    if not destination:
        logger.warning("sweep_deposit: destination_missing deal_id=%s", deal.id)
        raise ValueError("advertiser_wallet_missing")
    try:
        if payment.deposit_key:
            deposit_key = ton_escrow.decrypt_deposit_key(payment.deposit_key)
        else:
            deposit_key = ton_escrow.derive_deposit_key(deal.id)
        tx_hash = ton_escrow.send_sweep(deposit_key, destination)
        if tx_hash:
            payment.sweep_tx_hash = tx_hash
            log_event(db, deal.id, "ESCROW_SWEPT", {"tx_hash": tx_hash})
        else:
            payment.sweep_tx_hash = "SKIPPED_LOW_BALANCE"
            log_event(db, deal.id, "ESCROW_SWEEP_SKIPPED", {"reason": "low_balance"})
        payment.swept_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(payment)
        logger.info("sweep_deposit: success deal_id=%s tx_hash=%s", deal.id, tx_hash)
        return payment
    except ValueError:
        raise
    except Exception:
        logger.exception("sweep_deposit: error deal_id=%s", deal.id)
        raise
