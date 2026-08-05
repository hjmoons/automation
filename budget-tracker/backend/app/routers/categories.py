from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models import Category, CategoryUpdate

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


@router.patch("/{category_id}", response_model=Category)
def update_category(
    category_id: int, update: CategoryUpdate, session: Session = Depends(get_session)
):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    for key, value in update.dict(exclude_unset=True).items():
        setattr(category, key, value)
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: int, session: Session = Depends(get_session)):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    session.delete(category)
    session.commit()
