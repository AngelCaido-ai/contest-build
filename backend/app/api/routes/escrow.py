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
from app.services.escrow_service import _lock_row, create_deposit

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
    deal = _lock_row(db, Deal, Deal.id == deal_id)
    existing = _lock_row(db, EscrowPayment, EscrowPayment.deal_id == deal_id)
    if existing:
        return _enrich_escrow_out(existing, deal)
    if deal.status not in {DealStatus.TERMS_LOCKED, DealStatus.AWAITING_PAYMENT}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    try:
        payment = create_deposit(db, deal, payload.expected_amount)
        logger.info("create_deposit: success deal_id=%s user_id=%s", deal_id, user.id)
        return _enrich_escrow_out(payment, deal)
    except HTTPException:
        raise
    except Exception:
        logger.exception("create_deposit: error deal_id=%s user_id=%s", deal_id, user.id)
        raise


def _enrich_escrow_out(payment: EscrowPayment, deal: Deal) -> EscrowOut:
    out = EscrowOut.model_validate(payment)
    out.deal_price = float(deal.price) if deal.price is not None else None
    if out.expected_amount is not None and out.deal_price is not None:
        out.network_fee = round(out.expected_amount - out.deal_price, 8)
    return out
