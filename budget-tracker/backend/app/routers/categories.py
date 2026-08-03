from typing import List

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..database import get_session
from ..models import Category

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("/", response_model=List[Category])
def list_categories(session: Session = Depends(get_session)):
    return session.exec(select(Category)).all()


@router.post("/", response_model=Category)
def create_category(category: Category, session: Session = Depends(get_session)):
    session.add(category)
    session.commit()
    session.refresh(category)
    return category
