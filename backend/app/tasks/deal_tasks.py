from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.channel import Channel
from app.models.creative import Creative
from app.models.deal import Deal
from app.models.enums import DealStatus
from app.services.deal_service import log_event, set_status
from app.services.telegram_service import copy_message, send_message


def check_payment_timeouts() -> None:
    db: Session = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=settings.payment_timeout_minutes)
        deals = db.query(Deal).filter(Deal.status == DealStatus.AWAITING_PAYMENT, Deal.updated_at < cutoff).all()
        for deal in deals:
            set_status(deal, DealStatus.CANCELED)
            log_event(db, deal.id, "PAYMENT_TIMEOUT")
        db.commit()
    finally:
        db.close()


def process_scheduled_posts() -> None:
    db: Session = SessionLocal()
    try:
        now = datetime.utcnow()
        deals = (
            db.query(Deal)
            .filter(Deal.status.in_([DealStatus.APPROVED, DealStatus.SCHEDULED]), Deal.publish_at <= now)
            .all()
        )
        for deal in deals:
            channel = db.get(Channel, deal.channel_id)
            creative = (
                db.query(Creative)
                .filter(Creative.deal_id == deal.id)
                .order_by(Creative.version.desc())
                .first()
            )
            if not channel or not creative or not creative.text:
                continue
            message_id = send_message(channel.tg_chat_id, creative.text)
            if not message_id:
                continue
            deal.posted_message_id = message_id
            deal.posted_at = now
            deal.verification_started_at = now
            set_status(deal, DealStatus.VERIFYING)
            log_event(db, deal.id, "POSTED", {"message_id": message_id})
        db.commit()
    finally:
        db.close()


def check_deleted_posts() -> None:
    if settings.bot_log_chat_id is None:
        return
    db: Session = SessionLocal()
    try:
        deals = db.query(Deal).filter(Deal.status == DealStatus.VERIFYING, Deal.posted_message_id.isnot(None)).all()
        for deal in deals:
            channel = db.get(Channel, deal.channel_id)
            if not channel:
                continue
            ok = copy_message(channel.tg_chat_id, int(deal.posted_message_id), settings.bot_log_chat_id)
            if not ok:
                deal.deleted = True
                log_event(db, deal.id, "POST_DELETED", {"message_id": deal.posted_message_id})
        db.commit()
    finally:
        db.close()


def check_verification_windows() -> None:
    db: Session = SessionLocal()
    try:
        now = datetime.utcnow()
        deals = db.query(Deal).filter(Deal.status == DealStatus.VERIFYING).all()
        for deal in deals:
            window = deal.verification_window or settings.verification_window_minutes
            start = deal.verification_started_at or deal.posted_at
            if not start:
                continue
            if now < start + timedelta(minutes=window):
                continue
            if deal.tampered or deal.deleted:
                set_status(deal, DealStatus.REFUNDED)
                log_event(db, deal.id, "REFUNDED")
            else:
                set_status(deal, DealStatus.RELEASED)
                log_event(db, deal.id, "RELEASED")
        db.commit()
    finally:
        db.close()
