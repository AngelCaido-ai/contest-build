import logging

from app.models.deal import Deal
from app.models.deal_event import DealEvent
from app.models.enums import DealStatus

logger = logging.getLogger(__name__)

ALLOWED_TRANSITIONS: dict[DealStatus, set[DealStatus]] = {
    DealStatus.NEGOTIATING: {DealStatus.TERMS_LOCKED, DealStatus.CANCELED},
    DealStatus.TERMS_LOCKED: {DealStatus.TERMS_LOCKED, DealStatus.AWAITING_PAYMENT, DealStatus.CANCELED},
    DealStatus.AWAITING_PAYMENT: {DealStatus.FUNDED, DealStatus.CANCELED},
    DealStatus.FUNDED: {DealStatus.CREATIVE_DRAFT, DealStatus.CREATIVE_REVIEW, DealStatus.CANCELED, DealStatus.REFUNDED},
    DealStatus.CREATIVE_DRAFT: {DealStatus.CREATIVE_REVIEW, DealStatus.CANCELED},
    DealStatus.CREATIVE_REVIEW: {DealStatus.APPROVED, DealStatus.CREATIVE_DRAFT, DealStatus.CREATIVE_REVIEW, DealStatus.CANCELED},
    DealStatus.APPROVED: {DealStatus.SCHEDULED, DealStatus.POSTED, DealStatus.VERIFYING, DealStatus.CANCELED},
    DealStatus.SCHEDULED: {DealStatus.POSTED, DealStatus.VERIFYING, DealStatus.CANCELED},
    DealStatus.POSTED: {DealStatus.VERIFYING},
    DealStatus.VERIFYING: {DealStatus.RELEASED, DealStatus.REFUNDED},
}


class InvalidTransitionError(ValueError):
    def __init__(self, deal_id: int, current: DealStatus, target: DealStatus):
        self.deal_id = deal_id
        self.current = current
        self.target = target
        super().__init__(
            f"invalid transition deal_id={deal_id}: {current.value} -> {target.value}"
        )


def can_transition(current: DealStatus, new_status: DealStatus) -> bool:
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    return new_status in allowed


def set_status(deal: Deal, new_status: DealStatus) -> None:
    old_status = deal.status
    if not can_transition(old_status, new_status):
        raise InvalidTransitionError(deal.id, old_status, new_status)
    deal.status = new_status
    logger.info("deal status change: deal_id=%s %s -> %s", deal.id, old_status, new_status)


def log_event(db, deal_id: int, event_type: str, payload: dict | None = None) -> None:
    db.add(DealEvent(deal_id=deal_id, type=event_type, payload=payload))
    logger.info("deal event: deal_id=%s type=%s", deal_id, event_type)
