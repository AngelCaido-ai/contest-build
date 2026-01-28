from app.models.deal import Deal
from app.models.deal_event import DealEvent
from app.models.enums import DealStatus

ALLOWED_TRANSITIONS: dict[DealStatus, set[DealStatus]] = {
    DealStatus.NEGOTIATING: {DealStatus.TERMS_LOCKED, DealStatus.CANCELED},
    DealStatus.TERMS_LOCKED: {DealStatus.AWAITING_PAYMENT, DealStatus.CREATIVE_DRAFT, DealStatus.CANCELED},
    DealStatus.AWAITING_PAYMENT: {DealStatus.FUNDED, DealStatus.CANCELED},
    DealStatus.FUNDED: {DealStatus.CREATIVE_DRAFT, DealStatus.CANCELED},
    DealStatus.CREATIVE_DRAFT: {DealStatus.CREATIVE_REVIEW, DealStatus.CANCELED},
    DealStatus.CREATIVE_REVIEW: {DealStatus.APPROVED, DealStatus.CANCELED},
    DealStatus.APPROVED: {DealStatus.SCHEDULED, DealStatus.CANCELED},
    DealStatus.SCHEDULED: {DealStatus.POSTED, DealStatus.CANCELED},
    DealStatus.POSTED: {DealStatus.VERIFYING},
    DealStatus.VERIFYING: {DealStatus.RELEASED, DealStatus.REFUNDED},
}


def can_transition(current: DealStatus, new_status: DealStatus) -> bool:
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    return new_status in allowed


def set_status(deal: Deal, new_status: DealStatus) -> None:
    deal.status = new_status


def log_event(db, deal_id: int, event_type: str, payload: dict | None = None) -> None:
    db.add(DealEvent(deal_id=deal_id, type=event_type, payload=payload))
