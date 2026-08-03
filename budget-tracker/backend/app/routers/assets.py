from typing import List

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..database import get_session
from ..models import Asset

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("/", response_model=List[Asset])
def list_assets(session: Session = Depends(get_session)):
    return session.exec(select(Asset)).all()


@router.post("/", response_model=Asset)
def create_asset(asset: Asset, session: Session = Depends(get_session)):
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset
