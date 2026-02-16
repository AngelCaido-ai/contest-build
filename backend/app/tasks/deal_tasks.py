import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.channel import Channel
from app.models.creative import Creative
from app.models.deal import Deal
from app.models.escrow_payment import EscrowPayment
from app.models.enums import DealStatus
from app.services.deal_service import InvalidTransitionError, log_event, set_status
from app.services.escrow_service import _lock_row, refund_payment, release_payment, scan_incoming_payments, sweep_deposit
from app.services.telegram_service import copy_message, send_media, send_message

logger = logging.getLogger(__name__)


def check_payment_timeouts() -> None:
    logger.info("check_payment_timeouts: start")
    db: Session = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.payment_timeout_minutes)
        deals = db.query(Deal).filter(Deal.status == DealStatus.AWAITING_PAYMENT, Deal.updated_at < cutoff).all()
        logger.info("check_payment_timeouts: found %d expired deals", len(deals))
        for deal in deals:
            try:
                set_status(deal, DealStatus.CANCELED)
                log_event(db, deal.id, "PAYMENT_TIMEOUT")
                logger.info("check_payment_timeouts: canceled deal_id=%s", deal.id)
            except InvalidTransitionError:
                logger.warning("check_payment_timeouts: transition skipped deal_id=%s status=%s", deal.id, deal.status)
            except Exception:
                logger.exception("check_payment_timeouts: error canceling deal_id=%s", deal.id)
        db.commit()
        logger.info("check_payment_timeouts: done")
    except Exception:
        logger.exception("check_payment_timeouts: error")
    finally:
        db.close()


def scan_escrow_deposits() -> None:
    logger.info("scan_escrow_deposits: start")
    db: Session = SessionLocal()
    try:
        count = scan_incoming_payments(db)
        logger.info("scan_escrow_deposits: processed %d payments", count)
    except Exception:
        logger.exception("scan_escrow_deposits: error")
    finally:
        db.close()


def process_scheduled_posts() -> None:
    logger.info("process_scheduled_posts: start")
    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        deals = (
            db.query(Deal)
            .filter(Deal.status.in_([DealStatus.APPROVED, DealStatus.SCHEDULED]), Deal.publish_at <= now)
            .all()
        )
        logger.info("process_scheduled_posts: found %d deals to publish", len(deals))
        for deal in deals:
            try:
                channel = db.get(Channel, deal.channel_id)
                creative = (
                    db.query(Creative)
                    .filter(Creative.deal_id == deal.id)
                    .order_by(Creative.version.desc())
                    .first()
                )
                if not channel or not creative or (not creative.text and not creative.media_file_ids):
                    logger.warning("process_scheduled_posts: skip deal_id=%s (no channel/creative)", deal.id)
                    continue
                message_id = send_media(channel.tg_chat_id, creative.text, creative.media_file_ids)
                if not message_id and creative.text:
                    message_id = send_message(channel.tg_chat_id, creative.text)
                if not message_id:
                    logger.warning("process_scheduled_posts: failed to post deal_id=%s", deal.id)
                    continue
                deal.posted_message_id = message_id
                deal.posted_at = now
                deal.verification_started_at = now
                set_status(deal, DealStatus.VERIFYING)
                log_event(db, deal.id, "POSTED", {"message_id": message_id})
                logger.info("process_scheduled_posts: posted deal_id=%s message_id=%s", deal.id, message_id)
            except InvalidTransitionError:
                logger.warning("process_scheduled_posts: transition skipped deal_id=%s status=%s", deal.id, deal.status)
            except Exception:
                logger.exception("process_scheduled_posts: error posting deal_id=%s", deal.id)
        db.commit()
        logger.info("process_scheduled_posts: done")
    except Exception:
        logger.exception("process_scheduled_posts: error")
    finally:
        db.close()


def check_deleted_posts() -> None:
    if settings.bot_log_chat_id is None:
        return
    logger.info("check_deleted_posts: start")
    db: Session = SessionLocal()
    try:
        deals = db.query(Deal).filter(Deal.status == DealStatus.VERIFYING, Deal.posted_message_id.isnot(None)).all()
        logger.info("check_deleted_posts: checking %d deals", len(deals))
        for deal in deals:
            try:
                channel = db.get(Channel, deal.channel_id)
                if not channel:
                    continue
                ok = copy_message(channel.tg_chat_id, int(deal.posted_message_id), settings.bot_log_chat_id)
                if not ok:
                    deal.deleted = True
                    log_event(db, deal.id, "POST_DELETED", {"message_id": deal.posted_message_id})
                    logger.info("check_deleted_posts: deal_id=%s marked as deleted", deal.id)
            except Exception:
                logger.exception("check_deleted_posts: error checking deal_id=%s", deal.id)
        db.commit()
        logger.info("check_deleted_posts: done")
    except Exception:
        logger.exception("check_deleted_posts: error")
    finally:
        db.close()


def check_verification_windows() -> None:
    logger.info("check_verification_windows: start")
    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        deals = db.query(Deal).filter(Deal.status == DealStatus.VERIFYING).all()
        logger.info("check_verification_windows: checking %d deals", len(deals))
        for deal in deals:
            window = deal.verification_window or settings.verification_window_minutes
            start = deal.verification_started_at or deal.posted_at
            if not start:
                continue
            if now < start + timedelta(minutes=window):
                continue
            deal = _lock_row(db, Deal, Deal.id == deal.id)
            payment = _lock_row(db, EscrowPayment, EscrowPayment.deal_id == deal.id)
            if not deal or deal.status != DealStatus.VERIFYING:
                continue
            if not payment or not payment.tx_hash:
                continue
            if payment.release_tx_hash or payment.refund_tx_hash:
                continue
            if deal.tampered or deal.deleted:
                try:
                    refund_payment(db, deal, None, "verification_failed")
                    logger.info("check_verification_windows: refunded deal_id=%s", deal.id)
                except ValueError as exc:
                    log_event(db, deal.id, "ESCROW_REFUND_FAILED", {"error": str(exc)})
                    logger.warning("check_verification_windows: refund failed deal_id=%s error=%s", deal.id, exc)
                except Exception:
                    logger.exception("check_verification_windows: refund error deal_id=%s", deal.id)
            else:
                try:
                    release_payment(db, deal, None)
                    logger.info("check_verification_windows: released deal_id=%s", deal.id)
                except ValueError as exc:
                    log_event(db, deal.id, "ESCROW_RELEASE_FAILED", {"error": str(exc)})
                    logger.warning("check_verification_windows: release failed deal_id=%s error=%s", deal.id, exc)
                except Exception:
                    logger.exception("check_verification_windows: release error deal_id=%s", deal.id)
        db.commit()
        logger.info("check_verification_windows: done")
    except Exception:
        logger.exception("check_verification_windows: error")
    finally:
        db.close()


def sweep_completed_deposits() -> None:
    logger.info("sweep_completed_deposits: start")
    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=settings.sweep_delay_minutes)
        rows = (
            db.query(EscrowPayment, Deal)
            .join(Deal, Deal.id == EscrowPayment.deal_id)
            .filter(
                Deal.status.in_([DealStatus.RELEASED, DealStatus.REFUNDED]),
                EscrowPayment.sweep_tx_hash.is_(None),
                (
                    (EscrowPayment.released_at.isnot(None) & (EscrowPayment.released_at < cutoff))
                    | (EscrowPayment.refunded_at.isnot(None) & (EscrowPayment.refunded_at < cutoff))
                ),
            )
            .all()
        )
        logger.info("sweep_completed_deposits: found %d payments", len(rows))
        for payment, deal in rows:
            try:
                deal = _lock_row(db, Deal, Deal.id == deal.id)
                payment = _lock_row(db, EscrowPayment, EscrowPayment.id == payment.id)
                if not deal or not payment or payment.sweep_tx_hash:
                    continue
                sweep_deposit(db, deal, payment)
                logger.info("sweep_completed_deposits: swept deal_id=%s", deal.id)
            except ValueError as exc:
                log_event(db, deal.id, "ESCROW_SWEEP_FAILED", {"error": str(exc)})
                logger.warning("sweep_completed_deposits: sweep failed deal_id=%s error=%s", deal.id, exc)
            except Exception:
                logger.exception("sweep_completed_deposits: sweep error deal_id=%s", deal.id)
        logger.info("sweep_completed_deposits: done")
    except Exception:
        logger.exception("sweep_completed_deposits: error")
    finally:
        db.close()
