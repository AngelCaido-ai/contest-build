from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_bot_secret, get_db
from app.core.security import create_access_token, verify_init_data
from app.models.user import User
from app.schemas.auth import AuthRequest, AuthResponse, BotAuthRequest
from app.schemas.user import UserOut

router = APIRouter()


@router.post("/miniapp", response_model=AuthResponse)
def auth_miniapp(payload: AuthRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user_data = verify_init_data(payload.init_data)
    if not user_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    tg_user_id = user_data.get("id")
    if not tg_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    user = db.query(User).filter(User.tg_user_id == tg_user_id).first()
    if not user:
        user = User(tg_user_id=tg_user_id, roles=payload.roles or ["advertiser"])
        db.add(user)
        db.commit()
        db.refresh(user)
    token = create_access_token(user.id)
    return AuthResponse(token=token, user=UserOut.model_validate(user))


@router.post("/bot", response_model=AuthResponse, dependencies=[Depends(get_bot_secret)])
def auth_bot(payload: BotAuthRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.query(User).filter(User.tg_user_id == payload.tg_user_id).first()
    if not user:
        user = User(tg_user_id=payload.tg_user_id, roles=payload.roles or ["advertiser"])
        db.add(user)
        db.commit()
        db.refresh(user)
    token = create_access_token(user.id)
    return AuthResponse(token=token, user=UserOut.model_validate(user))
