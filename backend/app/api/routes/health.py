from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)) -> JSONResponse:
    checks: dict[str, str] = {}
    status_code = 200

    try:
        db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "fail"
        status_code = 503

    try:
        r = Redis.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "fail"
        status_code = 503

    checks["status"] = "ok" if status_code == 200 else "degraded"
    return JSONResponse(content=checks, status_code=status_code)
