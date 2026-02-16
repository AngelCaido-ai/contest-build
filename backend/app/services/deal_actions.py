import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.channel import Channel
from app.models.channel_manager import ChannelManager
from app.models.creative import Creative
from app.models.deal import Deal
from app.models.listing import Listing
from app.models.deal_event import DealEvent
from app.models.escrow_payment import EscrowPayment
from app.models.enums import CreativeStatus, DealStatus
from app.models.user import User
from app.services.deal_service import InvalidTransitionError, log_event, set_status
from app.services.escrow_service import create_deposit
from app.services.telegram_service import send_media, send_message

logger = logging.getLogger(__name__)

ROLE_OWNER = "owner"
ROLE_ADVERTISER = "advertiser"

ROLE_ALLOWED_STATUSES: dict[str, set[DealStatus]] = {
    ROLE_OWNER: {
        DealStatus.TERMS_LOCKED,
        DealStatus.CANCELED,
        DealStatus.SCHEDULED,
        DealStatus.POSTED,
        DealStatus.VERIFYING,
        DealStatus.RELEASED,
        DealStatus.REFUNDED,
    },
    ROLE_ADVERTISER: {
        DealStatus.AWAITING_PAYMENT,
        DealStatus.FUNDED,
        DealStatus.CANCELED,
    },
}

FINAL_DEAL_STATUSES = {
    DealStatus.RELEASED,
    DealStatus.REFUNDED,
    DealStatus.CANCELED,
}


def get_deal_role_flags(db: Session, deal: Deal, user_id: int) -> tuple[bool, bool]:
    channel = db.get(Channel, deal.channel_id)
    if not channel:
        raise ValueError("channel_not_found")
    is_owner = channel.owner_user_id == user_id
    if not is_owner:
        manager = (
            db.query(ChannelManager)
            .filter(ChannelManager.channel_id == channel.id, ChannelManager.user_id == user_id)
            .first()
        )
        is_owner = bool(manager)
    is_advertiser = deal.advertiser_id == user_id
    if not is_owner and not is_advertiser:
        raise ValueError("not_deal_participant")
    return is_owner, is_advertiser


def get_deal_role(db: Session, deal: Deal, user_id: int) -> str:
    is_owner, _ = get_deal_role_flags(db, deal, user_id)
    return ROLE_OWNER if is_owner else ROLE_ADVERTISER


def next_step_for_role(status_value: DealStatus, role: str) -> str | None:
    if status_value == DealStatus.NEGOTIATING:
        return "Lock terms or cancel the deal." if role == ROLE_OWNER else "Wait for owner to lock terms."
    if status_value == DealStatus.TERMS_LOCKED:
        return "Wait for payment." if role == ROLE_OWNER else "Pay escrow (open Payment details)."
    if status_value == DealStatus.AWAITING_PAYMENT:
        return "Wait for payment." if role == ROLE_OWNER else "Send payment to escrow."
    if status_value == DealStatus.FUNDED:
        return "Create and submit creative." if role == ROLE_OWNER else "Wait for creative."
    if status_value == DealStatus.CREATIVE_DRAFT:
        return "Update creative and submit for review." if role == ROLE_OWNER else "Wait for creative."
    if status_value == DealStatus.CREATIVE_REVIEW:
        return "Review creative and approve/request edits." if role == ROLE_ADVERTISER else "Waiting for review."
    if status_value == DealStatus.APPROVED:
        return "Schedule the post." if role == ROLE_OWNER else "Waiting for schedule."
    if status_value == DealStatus.SCHEDULED:
        return "Post at scheduled time." if role == ROLE_OWNER else "Waiting for post."
    if status_value == DealStatus.POSTED:
        return "Start verification." if role == ROLE_OWNER else "Waiting for verification."
    if status_value == DealStatus.VERIFYING:
        return "Release or refund after verification window." if role == ROLE_OWNER else "Waiting for release/refund."
    return None


def format_deal_terms(deal: Deal) -> str:
    lines = []
    if deal.price is not None:
        lines.append(f"price: {deal.price}")
    if deal.format:
        lines.append(f"format: {deal.format}")
    if deal.publish_at:
        lines.append(f"publish_at: {deal.publish_at.isoformat()}")
    if deal.verification_window:
        lines.append(f"verification_window: {deal.verification_window}")
    if deal.brief:
        lines.append(f"brief: {deal.brief}")
    if not lines:
        return "terms: -"
    return "terms:\n" + "\n".join(lines)


def deal_action_keyboard(deal: Deal, role: str) -> dict | None:
    buttons = [[{"text": "Open deal", "callback_data": f"deal:{deal.id}"}]]
    if role == ROLE_ADVERTISER and deal.status in {DealStatus.TERMS_LOCKED, DealStatus.AWAITING_PAYMENT}:
        buttons.append([{"text": "Payment details", "callback_data": f"deal_payment:{deal.id}"}])
    return {"inline_keyboard": buttons}


def send_deal_notification(deal: Deal, user: User, role: str, text: str) -> None:
    if not user.tg_user_id:
        return
    next_step = next_step_for_role(deal.status, role)
    message = text
    if next_step:
        message = f"{message}\nNext step: {next_step}"
    reply_markup = deal_action_keyboard(deal, role)
    send_message(int(user.tg_user_id), message, reply_markup=reply_markup)


def notify_deal_parties(db: Session, deal: Deal, text: str) -> None:
    advertiser = db.get(User, deal.advertiser_id)
    channel = db.get(Channel, deal.channel_id)
    owner = db.get(User, channel.owner_user_id) if channel else None
    if advertiser:
        send_deal_notification(deal, advertiser, ROLE_ADVERTISER, text)
    if owner:
        send_deal_notification(deal, owner, ROLE_OWNER, text)


def send_creative_to_advertiser(deal: Deal, creative: Creative, advertiser: User | None) -> None:
    if not advertiser or not advertiser.tg_user_id:
        return
    send_media(int(advertiser.tg_user_id), creative.text, creative.media_file_ids)


def do_update_terms(db: Session, deal_id: int, actor_user_id: int, fields: dict) -> Deal:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise ValueError("deal_not_found")
    role = get_deal_role(db, deal, actor_user_id)
    if role != ROLE_OWNER:
        raise ValueError("forbidden")
    if deal.status not in {DealStatus.NEGOTIATING, DealStatus.TERMS_LOCKED}:
        raise ValueError("invalid_status")
    if deal.listing_id is not None and "price" in fields:
        listing = db.get(Listing, deal.listing_id)
        if listing and listing.price_usd is not None:
            fields.pop("price")
    log_payload = {k: v.isoformat() if isinstance(v, datetime) else v for k, v in fields.items()}
    for key, value in fields.items():
        setattr(deal, key, value)
    set_status(deal, DealStatus.TERMS_LOCKED)
    log_event(db, deal.id, "TERMS_LOCKED", log_payload)
    db.commit()
    db.refresh(deal)
    advertiser = db.get(User, deal.advertiser_id)
    channel = db.get(Channel, deal.channel_id)
    owner = db.get(User, channel.owner_user_id) if channel else None
    if owner:
        send_deal_notification(deal, owner, ROLE_OWNER, f"Deal #{deal.id}: terms locked.")
    if advertiser:
        terms_text = format_deal_terms(deal)
        send_deal_notification(
            deal, advertiser, ROLE_ADVERTISER, f"Deal #{deal.id}: terms locked.\n\n{terms_text}"
        )
    return deal


def do_update_publish_at(db: Session, deal_id: int, actor_user_id: int, publish_at: datetime) -> Deal:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise ValueError("deal_not_found")
    role = get_deal_role(db, deal, actor_user_id)
    if role != ROLE_OWNER:
        raise ValueError("forbidden")
    if deal.status in {
        DealStatus.POSTED,
        DealStatus.VERIFYING,
        DealStatus.RELEASED,
        DealStatus.REFUNDED,
        DealStatus.CANCELED,
    }:
        raise ValueError("invalid_status")
    deal.publish_at = publish_at
    log_event(db, deal.id, "PUBLISH_AT_UPDATED", {"publish_at": publish_at.isoformat()})
    db.commit()
    db.refresh(deal)
    notify_deal_parties(db, deal, f"Deal #{deal.id}: publish_at -> {publish_at.isoformat()}.")
    return deal


def do_update_status(db: Session, deal_id: int, actor_user_id: int, new_status: DealStatus) -> Deal:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise ValueError("deal_not_found")
    role = get_deal_role(db, deal, actor_user_id)
    allowed = ROLE_ALLOWED_STATUSES.get(role, set())
    if new_status not in allowed:
        raise ValueError("forbidden")
    if new_status == DealStatus.AWAITING_PAYMENT:
        existing = db.query(EscrowPayment).filter(EscrowPayment.deal_id == deal_id).first()
        if not existing:
            create_deposit(db, deal, deal.price)
    else:
        set_status(deal, new_status)
    log_event(db, deal.id, "STATUS_UPDATED", {"status": new_status})
    db.commit()
    db.refresh(deal)
    notify_deal_parties(db, deal, f"Deal #{deal.id}: status -> {new_status.value}.")
    return deal


def do_create_creative(
    db: Session,
    deal_id: int,
    actor_user_id: int,
    text: str | None,
    media_file_ids: list | None,
) -> Creative:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise ValueError("deal_not_found")
    is_owner, _ = get_deal_role_flags(db, deal, actor_user_id)
    if not is_owner:
        raise ValueError("forbidden")
    if deal.status not in {DealStatus.FUNDED, DealStatus.CREATIVE_DRAFT}:
        raise ValueError("invalid_status")
    if not text and not media_file_ids:
        raise ValueError("empty_creative")
    existing = db.query(Creative).filter(Creative.deal_id == deal_id).order_by(Creative.version.desc()).first()
    version = 1 if not existing else existing.version + 1
    creative = Creative(
        deal_id=deal_id,
        text=text,
        media_file_ids=media_file_ids,
        version=version,
        status=CreativeStatus.REVIEW,
    )
    db.add(creative)
    set_status(deal, DealStatus.CREATIVE_REVIEW)
    log_event(db, deal.id, "CREATIVE_SUBMITTED", {"version": version})
    db.commit()
    db.refresh(creative)
    notify_deal_parties(db, deal, f"Deal #{deal.id}: creative drafted v{version}.")
    send_creative_to_advertiser(deal, creative, db.get(User, deal.advertiser_id))
    return creative


def do_get_creative(db: Session, deal_id: int, actor_user_id: int, version: int | None) -> Creative:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise ValueError("deal_not_found")
    get_deal_role_flags(db, deal, actor_user_id)
    query = db.query(Creative).filter(Creative.deal_id == deal_id)
    if version is not None:
        creative = query.filter(Creative.version == version).first()
    else:
        creative = query.order_by(Creative.version.desc()).first()
    if not creative:
        raise ValueError("creative_not_found")
    return creative


def do_update_creative_status(
    db: Session,
    deal_id: int,
    actor_user_id: int,
    new_status: CreativeStatus,
    comment: str | None,
    publish_at: datetime | None,
) -> Creative:
    creative = db.query(Creative).filter(Creative.deal_id == deal_id).order_by(Creative.version.desc()).first()
    if not creative:
        raise ValueError("creative_not_found")
    deal = db.get(Deal, deal_id)
    if not deal:
        raise ValueError("deal_not_found")
    _, is_advertiser = get_deal_role_flags(db, deal, actor_user_id)
    if not is_advertiser:
        raise ValueError("forbidden")
    if deal.status != DealStatus.CREATIVE_REVIEW:
        raise ValueError("invalid_status")
    comment = (comment or "").strip() or None
    if new_status == CreativeStatus.DRAFT and not comment:
        raise ValueError("comment_required")
    if publish_at is not None:
        deal.publish_at = publish_at
    if new_status == CreativeStatus.APPROVED and deal.publish_at is None:
        raise ValueError("publish_at_required")
    creative.status = new_status
    if new_status == CreativeStatus.APPROVED:
        set_status(deal, DealStatus.APPROVED)
    elif new_status == CreativeStatus.DRAFT:
        set_status(deal, DealStatus.CREATIVE_DRAFT)
    elif new_status == CreativeStatus.REVIEW:
        set_status(deal, DealStatus.CREATIVE_REVIEW)
    log_payload: dict = {"status": new_status}
    if comment:
        log_payload["comment"] = comment
    if publish_at is not None:
        log_payload["publish_at"] = publish_at.isoformat()
    log_event(db, deal.id, "CREATIVE_STATUS", log_payload)
    db.commit()
    db.refresh(creative)
    notify_deal_parties(db, deal, f"Deal #{deal.id}: creative status -> {new_status.value}.")
    if new_status == CreativeStatus.DRAFT and comment:
        channel = db.get(Channel, deal.channel_id)
        owner = db.get(User, channel.owner_user_id) if channel else None
        if owner:
            send_deal_notification(
                deal, owner, ROLE_OWNER, f"Deal #{deal.id}: edits requested. Comment: {comment}"
            )
    return creative


def do_add_advertiser_brief(
    db: Session,
    deal_id: int,
    actor_user_id: int,
    text: str | None,
    media_file_ids: list | None,
    publish_at: datetime | None,
) -> DealEvent:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise ValueError("deal_not_found")
    _, is_advertiser = get_deal_role_flags(db, deal, actor_user_id)
    if not is_advertiser:
        raise ValueError("forbidden")
    if not text and not media_file_ids and publish_at is None:
        raise ValueError("empty_brief")
    if publish_at is not None:
        if deal.status in {
            DealStatus.POSTED,
            DealStatus.VERIFYING,
            DealStatus.RELEASED,
            DealStatus.REFUNDED,
            DealStatus.CANCELED,
        }:
            raise ValueError("invalid_status")
        deal.publish_at = publish_at
        log_event(db, deal.id, "PUBLISH_AT_REQUESTED", {"publish_at": publish_at.isoformat()})
    event_payload: dict = {
        "text": text,
        "media_file_ids": media_file_ids,
    }
    if publish_at is not None:
        event_payload["publish_at"] = publish_at.isoformat()
    event = DealEvent(deal_id=deal_id, type="ADVERTISER_BRIEF", payload=event_payload)
    db.add(event)
    db.commit()
    db.refresh(event)
    channel = db.get(Channel, deal.channel_id)
    owner = db.get(User, channel.owner_user_id) if channel else None
    if owner and owner.tg_user_id:
        lines = [f"Deal #{deal.id}: advertiser brief received."]
        if text:
            lines.append(f"brief: {text}")
        if publish_at is not None:
            lines.append(f"publish_at: {publish_at.isoformat()}")
        send_media(int(owner.tg_user_id), "\n".join(lines), media_file_ids)
        send_deal_notification(deal, owner, ROLE_OWNER, f"Deal #{deal.id}: advertiser brief received.")
    return event
