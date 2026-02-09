import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import auth, bot_actions, channels, deals, escrow, listings, requests, stats
from app.core.config import settings
from app.services import ton_escrow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

_default_origins = ["http://localhost:5173", "http://localhost:3000"]
_extra_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _extra_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(channels.router, prefix="/channels", tags=["channels"])
app.include_router(listings.router, prefix="/listings", tags=["listings"])
app.include_router(requests.router, prefix="/requests", tags=["requests"])
app.include_router(deals.router, prefix="/deals", tags=["deals"])
app.include_router(escrow.router, prefix="/escrow", tags=["escrow"])
app.include_router(stats.router, prefix="/stats", tags=["stats"])
app.include_router(bot_actions.router, prefix="/bot", tags=["bot"])


@app.on_event("startup")
def validate_escrow_secret_key() -> None:
    try:
        ton_escrow.ensure_escrow_secret_key()
        logger.info("escrow secret key validated")
    except Exception:
        logger.exception("failed to validate escrow secret key")
        raise
