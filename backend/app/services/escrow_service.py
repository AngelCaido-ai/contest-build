import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.deal import Deal
from app.models.escrow_payment import EscrowPayment
from app.models.enums import DealStatus
from app.services.deal_service import log_event, set_status


def create_deposit(db: Session, deal: Deal, expected_amount: float | None) -> EscrowPayment:
    deposit_address = f"TON-{uuid.uuid4().hex}"
    payment = EscrowPayment(
        deal_id=deal.id,
        deposit_address=deposit_address,
        expected_amount=expected_amount,
    )
    db.add(payment)
    set_status(deal, DealStatus.AWAITING_PAYMENT)
    log_event(db, deal.id, "ESCROW_CREATED", {"deposit_address": deposit_address})
    db.commit()
    db.refresh(payment)
    return payment


def confirm_payment(db: Session, deal: Deal, payment: EscrowPayment, tx_hash: str) -> EscrowPayment:
    payment.tx_hash = tx_hash
    payment.confirmed_at = datetime.utcnow()
    set_status(deal, DealStatus.FUNDED)
    log_event(db, deal.id, "ESCROW_FUNDED", {"tx_hash": tx_hash})
    db.commit()
    db.refresh(payment)
    return payment
