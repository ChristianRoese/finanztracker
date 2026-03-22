from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, col, select

from backend.database import get_session
from backend.models.etf import ETFPosition, ETFPurchase
from backend.services.etf_service import get_etf_forecast, get_portfolio_summary, refresh_all_prices

router = APIRouter(prefix="/api/etf", tags=["etf"])

SessionDep = Annotated[Session, Depends(get_session)]


class ETFPositionCreate(BaseModel):
    isin: str = Field(min_length=1)
    name: str = Field(min_length=1)
    wkn: str = ""
    ticker: str = ""
    monthly_amount: float = 0.0


@router.get("/positions")
def get_positions(session: SessionDep) -> list[dict]:
    return get_portfolio_summary(session)


@router.post("/positions", status_code=201)
def create_position(
    body: ETFPositionCreate,
    session: SessionDep,
) -> ETFPosition:
    existing = session.exec(select(ETFPosition).where(ETFPosition.isin == body.isin)).first()
    if existing:
        raise HTTPException(409, f"Position mit ISIN {body.isin} existiert bereits")
    pos = ETFPosition(isin=body.isin, name=body.name, wkn=body.wkn, ticker=body.ticker, monthly_amount=body.monthly_amount)
    session.add(pos)
    session.commit()
    session.refresh(pos)
    return pos


@router.post("/refresh-prices")
def refresh_prices(session: SessionDep) -> dict:
    updated = refresh_all_prices(session)
    return {"updated": updated, "count": len(updated)}


@router.get("/purchases")
def get_purchases(session: SessionDep) -> list[ETFPurchase]:
    purchases = session.exec(
        select(ETFPurchase).order_by(col(ETFPurchase.date).desc())
    ).all()
    return list(purchases)


@router.get("/forecast")
def get_forecast(session: SessionDep) -> dict:
    """5-Jahres-Prognose für alle ETF-Positionen (Best/Casual/Worst)."""
    return get_etf_forecast(session)
