from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Category(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    parent_id: Optional[int] = Field(default=None, foreign_key="category.id")
    monthly_budget: Optional[int] = None


class Asset(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    type: str  # cash | bank | card
    currency: str = "KRW"
    balance: Optional[int] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: datetime
    title: str
    amount: int
    type: str  # income | expense | transfer
    category_id: Optional[int] = Field(default=None, foreign_key="category.id")
    asset_id: Optional[int] = Field(default=None, foreign_key="asset.id")
    to_asset_id: Optional[int] = Field(default=None, foreign_key="asset.id")
    source: str  # sms_auto | photo_auto | manual
    receipt_image_path: Optional[str] = None
    memo: Optional[str] = None
    confirmed: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TransactionCreate(SQLModel):
    date: datetime
    title: str
    amount: int
    type: str
    category_id: Optional[int] = None
    asset_id: Optional[int] = None
    to_asset_id: Optional[int] = None
    source: str
    receipt_image_path: Optional[str] = None
    memo: Optional[str] = None
    confirmed: bool = False


class TransactionUpdate(SQLModel):
    title: Optional[str] = None
    amount: Optional[int] = None
    type: Optional[str] = None
    category_id: Optional[int] = None
    asset_id: Optional[int] = None
    to_asset_id: Optional[int] = None
    memo: Optional[str] = None
    confirmed: Optional[bool] = None
