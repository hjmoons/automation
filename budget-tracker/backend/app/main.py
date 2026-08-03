from fastapi import FastAPI

from .database import init_db
from .models import Asset, Category, Transaction  # noqa: F401
from .routers import assets, categories, transactions

app = FastAPI(title="Budget Tracker API")

app.include_router(categories.router)
app.include_router(assets.router)
app.include_router(transactions.router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
