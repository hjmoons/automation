from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..database import get_session
from ..models import Budget, BudgetCreate, BudgetUpdate

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("/", response_model=List[Budget])
def list_budgets(
    year: Optional[int] = Query(default=None),
    month: Optional[int] = Query(default=None),
    session: Session = Depends(get_session),
):
    query = select(Budget)
    if year is not None:
        query = query.where(Budget.year == year)
    if month is not None:
        query = query.where(Budget.month == month)
    return session.exec(query).all()


@router.post("/", response_model=Budget)
def create_budget(budget: BudgetCreate, session: Session = Depends(get_session)):
    row = Budget.from_orm(budget)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.patch("/{budget_id}", response_model=Budget)
def update_budget(
    budget_id: int, update: BudgetUpdate, session: Session = Depends(get_session)
):
    budget = session.get(Budget, budget_id)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    for key, value in update.dict(exclude_unset=True).items():
        setattr(budget, key, value)
    session.add(budget)
    session.commit()
    session.refresh(budget)
    return budget


@router.delete("/{budget_id}", status_code=204)
def delete_budget(budget_id: int, session: Session = Depends(get_session)):
    budget = session.get(Budget, budget_id)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    session.delete(budget)
    session.commit()
