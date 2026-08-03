from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models import Transaction, TransactionCreate, TransactionUpdate

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/", response_model=List[Transaction])
def list_transactions(session: Session = Depends(get_session)):
    return session.exec(select(Transaction).order_by(Transaction.date.desc())).all()


@router.post("/", response_model=Transaction)
def create_transaction(payload: TransactionCreate, session: Session = Depends(get_session)):
    transaction = Transaction.from_orm(payload)
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return transaction


@router.patch("/{transaction_id}", response_model=Transaction)
def update_transaction(
    transaction_id: int, update: TransactionUpdate, session: Session = Depends(get_session)
):
    transaction = session.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    for key, value in update.dict(exclude_unset=True).items():
        setattr(transaction, key, value)
    transaction.updated_at = datetime.utcnow()
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return transaction
