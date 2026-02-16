import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.request import Request
from app.schemas.request import RequestCreate, RequestOut, RequestUpdate

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=RequestOut)
def create_request(
    payload: RequestCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> RequestOut:
    try:
        item = Request(
            advertiser_id=user.id,
            budget=payload.budget,
            niche=payload.niche,
            languages=payload.languages,
            min_subs=payload.min_subs,
            min_views=payload.min_views,
            dates=payload.dates,
            brief=payload.brief,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        logger.info("create_request: success request_id=%s user_id=%s", item.id, user.id)
        return RequestOut.model_validate(item)
    except HTTPException:
        raise
    except Exception:
        logger.exception("create_request: error user_id=%s", user.id)
        raise


@router.get("/", response_model=list[RequestOut])
def list_requests(
    budget_min: float | None = Query(default=None),
    budget_max: float | None = Query(default=None),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> list[RequestOut]:
    query = db.query(Request)
    if budget_min is not None:
        query = query.filter(Request.budget >= budget_min)
    if budget_max is not None:
        query = query.filter(Request.budget <= budget_max)
    items = query.order_by(Request.created_at.desc()).offset(offset).limit(limit).all()
    return [RequestOut.model_validate(item) for item in items]


@router.get("/{request_id}", response_model=RequestOut)
def get_request(request_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)) -> RequestOut:
    item = db.get(Request, request_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return RequestOut.model_validate(item)


@router.patch("/{request_id}", response_model=RequestOut)
def update_request(
    request_id: int,
    payload: RequestUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> RequestOut:
    item = db.get(Request, request_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if item.advertiser_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    try:
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(item, key, value)
        db.commit()
        db.refresh(item)
        logger.info("update_request: success request_id=%s user_id=%s", request_id, user.id)
        return RequestOut.model_validate(item)
    except HTTPException:
        raise
    except Exception:
        logger.exception("update_request: error request_id=%s user_id=%s", request_id, user.id)
        raise
