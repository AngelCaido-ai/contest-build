import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.rate_limit import get_user_id_key, limiter
from app.models.channel import Channel
from app.models.deal import Deal
from app.models.escrow_payment import EscrowPayment
from app.models.enums import DealStatus
from app.schemas.escrow import EscrowDepositRequest, EscrowOut
from app.services.escrow_service import create_deposit

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
