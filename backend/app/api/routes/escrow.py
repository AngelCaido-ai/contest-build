import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_bot_secret, get_current_user, get_db
from app.core.config import settings
from app.core.rate_limit import get_user_id_key, limiter
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

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/deals/{deal_id}/deposit", response_model=EscrowOut)
@limiter.limit(settings.rate_limit_escrow_deposit, key_func=get_user_id_key)
def create_deposit_address(
    request: Request,
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
    try:
        payment = create_deposit(db, deal, payload.expected_amount)
        logger.info("create_deposit: success deal_id=%s user_id=%s", deal_id, user.id)
        return EscrowOut.model_validate(payment)
    except HTTPException:
        raise
    except Exception:
        logger.exception("create_deposit: error deal_id=%s user_id=%s", deal_id, user.id)
        raise


@router.post(
    "/deals/{deal_id}/confirm",
    response_model=EscrowOut,
    dependencies=[Depends(get_bot_secret)],
)
@limiter.limit(settings.rate_limit_escrow_bot)
def confirm_deposit(
    request: Request,
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
    try:
        updated = confirm_payment(db, deal, payment, payload.tx_hash)
        logger.info("confirm_deposit: success deal_id=%s tx_hash=%s", deal_id, payload.tx_hash)
        return EscrowOut.model_validate(updated)
    except HTTPException:
        raise
    except Exception:
        logger.exception("confirm_deposit: error deal_id=%s", deal_id)
        raise


@router.post(
    "/deals/{deal_id}/release",
    response_model=EscrowOut,
    dependencies=[Depends(get_bot_secret)],
)
@limiter.limit(settings.rate_limit_escrow_bot)
def release_escrow(
    request: Request,
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
        logger.info("release_escrow: success deal_id=%s", deal_id)
        return EscrowOut.model_validate(updated)
    except ValueError as exc:
        logger.warning("release_escrow: validation error deal_id=%s error=%s", deal_id, exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception:
        logger.exception("release_escrow: error deal_id=%s", deal_id)
        raise


@router.post(
    "/deals/{deal_id}/refund",
    response_model=EscrowOut,
    dependencies=[Depends(get_bot_secret)],
)
@limiter.limit(settings.rate_limit_escrow_bot)
def refund_escrow(
    request: Request,
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
        logger.info("refund_escrow: success deal_id=%s reason=%s", deal_id, payload.reason)
        return EscrowOut.model_validate(updated)
    except ValueError as exc:
        logger.warning("refund_escrow: validation error deal_id=%s error=%s", deal_id, exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception:
        logger.exception("refund_escrow: error deal_id=%s", deal_id)
        raise
