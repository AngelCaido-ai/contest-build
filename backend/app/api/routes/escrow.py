from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_bot_secret, get_current_user, get_db
from app.models.channel import Channel
from app.models.deal import Deal
from app.models.escrow_payment import EscrowPayment
from app.models.enums import DealStatus
from app.schemas.escrow import (
    EscrowConfirmRequest,
    EscrowDepositRequest,
    EscrowOut,
    EscrowRefundRequest,
    EscrowReleaseRequest,
)
from app.services.escrow_service import confirm_payment, create_deposit, refund_payment, release_payment

router = APIRouter()


@router.post("/deals/{deal_id}/deposit", response_model=EscrowOut)
def create_deposit_address(
    deal_id: int,
    payload: EscrowDepositRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> EscrowOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    channel = db.get(Channel, deal.channel_id)
    if deal.advertiser_id != user.id and (not channel or channel.owner_user_id != user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    existing = db.query(EscrowPayment).filter(EscrowPayment.deal_id == deal_id).first()
    if existing:
        return EscrowOut.model_validate(existing)
    if deal.status not in {DealStatus.TERMS_LOCKED, DealStatus.AWAITING_PAYMENT}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    payment = create_deposit(db, deal, payload.expected_amount)
    return EscrowOut.model_validate(payment)


@router.post(
    "/deals/{deal_id}/confirm",
    response_model=EscrowOut,
    dependencies=[Depends(get_bot_secret)],
)
def confirm_deposit(
    deal_id: int,
    payload: EscrowConfirmRequest,
    db: Session = Depends(get_db),
) -> EscrowOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    payment = db.query(EscrowPayment).filter(EscrowPayment.deal_id == deal_id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    updated = confirm_payment(db, deal, payment, payload.tx_hash)
    return EscrowOut.model_validate(updated)


@router.post(
    "/deals/{deal_id}/release",
    response_model=EscrowOut,
    dependencies=[Depends(get_bot_secret)],
)
def release_escrow(
    deal_id: int,
    payload: EscrowReleaseRequest,
    db: Session = Depends(get_db),
) -> EscrowOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    payment = db.query(EscrowPayment).filter(EscrowPayment.deal_id == deal_id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        updated = release_payment(db, deal, payload.payout_address)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return EscrowOut.model_validate(updated)


@router.post(
    "/deals/{deal_id}/refund",
    response_model=EscrowOut,
    dependencies=[Depends(get_bot_secret)],
)
def refund_escrow(
    deal_id: int,
    payload: EscrowRefundRequest,
    db: Session = Depends(get_db),
) -> EscrowOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    payment = db.query(EscrowPayment).filter(EscrowPayment.deal_id == deal_id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        updated = refund_payment(db, deal, payload.refund_address, payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return EscrowOut.model_validate(updated)
