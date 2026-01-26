from fastapi import FastAPI

from app.api.routes import auth, bot_actions, channels, deals, escrow, listings, requests, stats
from app.core.config import settings

app = FastAPI(title=settings.app_name)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(channels.router, prefix="/channels", tags=["channels"])
app.include_router(listings.router, prefix="/listings", tags=["listings"])
app.include_router(requests.router, prefix="/requests", tags=["requests"])
app.include_router(deals.router, prefix="/deals", tags=["deals"])
app.include_router(escrow.router, prefix="/escrow", tags=["escrow"])
app.include_router(stats.router, prefix="/stats", tags=["stats"])
app.include_router(bot_actions.router, prefix="/bot", tags=["bot"])
