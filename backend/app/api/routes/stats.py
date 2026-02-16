import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.channel import Channel
from app.models.channel_manager import ChannelManager
from app.models.channel_stats import ChannelStats
from app.schemas.channel_stats import ChannelStatsOut
from app.services.stats_service import fetch_bot_api_subscribers, fetch_stats

logger = logging.getLogger(__name__)
router = APIRouter()


def _can_access_channel(db: Session, channel: Channel, user) -> bool:
    if channel.owner_user_id == user.id:
        return True
    return (
        db.query(ChannelManager)
        .filter(ChannelManager.channel_id == channel.id, ChannelManager.user_id == user.id)
        .first()
    ) is not None


@router.post("/channels/{channel_id}/refresh", response_model=ChannelStatsOut)
def refresh_stats(
    channel_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> ChannelStatsOut:
    channel = db.get(Channel, channel_id)
    if not channel or not _can_access_channel(db, channel, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    raw = fetch_stats(channel.tg_chat_id, channel.username)
    source = None
    parsed: dict = {}
    if raw:
        parsed = raw.get("_parsed", {})
        subscribers = parsed.get("subscribers")
        views_per_post = parsed.get("views_per_post")
        if not views_per_post and raw.get("_views_from_posts"):
            parsed["views_per_post"] = raw["_views_from_posts"]
        source = "mtproto"
    else:
        subscribers = fetch_bot_api_subscribers(channel.tg_chat_id)
        parsed = {"subscribers": subscribers}
        source = "bot_api"
    logger.info(
        "refresh_stats: channel_id=%s source=%s parsed=%s",
        channel_id, source, parsed,
    )
    if parsed.get("subscribers") is None and parsed.get("views_per_post") is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    existing = db.query(ChannelStats).filter(ChannelStats.channel_id == channel_id).first()
    if not existing:
        existing = ChannelStats(channel_id=channel_id)
        db.add(existing)
    existing.subscribers = int(parsed["subscribers"]) if parsed.get("subscribers") is not None else None
    existing.views_per_post = parsed.get("views_per_post")
    existing.shares_per_post = parsed.get("shares_per_post")
    existing.reactions_per_post = parsed.get("reactions_per_post")
    existing.enabled_notifications = parsed.get("enabled_notifications")
    existing.subscribers_prev = int(parsed["subscribers_prev"]) if parsed.get("subscribers_prev") is not None else None
    existing.views_per_post_prev = parsed.get("views_per_post_prev")
    existing.shares_per_post_prev = parsed.get("shares_per_post_prev")
    existing.reactions_per_post_prev = parsed.get("reactions_per_post_prev")
    existing.languages_json = parsed.get("languages") if raw else None
    existing.premium_json = raw.get("premium_graph") if raw else None
    existing.updated_at = datetime.utcnow()
    existing.source = source
    db.commit()
    db.refresh(existing)
    return ChannelStatsOut.model_validate(existing)
