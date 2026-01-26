from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.request import Request
from app.schemas.request import RequestCreate, RequestOut, RequestUpdate

router = APIRouter()


@router.post("/", response_model=RequestOut)
def create_request(
    payload: RequestCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> RequestOut:
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
    return RequestOut.model_validate(item)


@router.get("/", response_model=list[RequestOut])
def list_requests(
    budget_min: float | None = Query(default=None),
    budget_max: float | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[RequestOut]:
    query = db.query(Request)
    if budget_min is not None:
        query = query.filter(Request.budget >= budget_min)
    if budget_max is not None:
        query = query.filter(Request.budget <= budget_max)
    items = query.all()
    return [RequestOut.model_validate(item) for item in items]


@router.get("/{request_id}", response_model=RequestOut)
def get_request(request_id: int, db: Session = Depends(get_db)) -> RequestOut:
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
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return RequestOut.model_validate(item)
