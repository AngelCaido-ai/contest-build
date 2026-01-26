from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.channel import Channel
from app.models.channel_stats import ChannelStats
from app.schemas.channel_stats import ChannelStatsOut
from app.services.stats_service import fetch_bot_api_subscribers, fetch_stats

router = APIRouter()


@router.post("/channels/{channel_id}/refresh", response_model=ChannelStatsOut)
def refresh_stats(
    channel_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> ChannelStatsOut:
    channel = db.get(Channel, channel_id)
    if not channel or channel.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    stats = fetch_stats(channel.tg_chat_id)
    subscribers = None
    views_per_post = None
    languages_json = None
    premium_json = None
    source = None
    if stats:
        subscribers = stats.get("followers", {}).get("current")
        views_per_post = stats.get("views_per_post", {}).get("current")
        languages_json = stats.get("languages_graph")
        premium_json = stats.get("premium_graph")
        source = "mtproto"
    else:
        subscribers = fetch_bot_api_subscribers(channel.tg_chat_id)
        source = "bot_api"
    if subscribers is None and views_per_post is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    existing = db.query(ChannelStats).filter(ChannelStats.channel_id == channel_id).first()
    if not existing:
        existing = ChannelStats(channel_id=channel_id)
        db.add(existing)
    existing.subscribers = subscribers
    existing.views_per_post = views_per_post
    existing.languages_json = languages_json
    existing.premium_json = premium_json
    existing.updated_at = datetime.utcnow()
    existing.source = source
    db.commit()
    db.refresh(existing)
    return ChannelStatsOut.model_validate(existing)
