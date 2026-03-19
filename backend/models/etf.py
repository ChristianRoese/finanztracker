from datetime import date, datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class ETFPosition(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    isin: str = Field(index=True, unique=True)
    wkn: str = ""
    name: str
    ticker: str = ""                      # yfinance ticker (z.B. "XDWD.DE")
    monthly_amount: float = 0.0           # aktueller Sparplan-Betrag EUR


class ETFPurchase(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    position_id: int = Field(foreign_key="etfposition.id")
    date: date
    price_eur: float
    shares: float
    total_eur: float
    source: str = "import"               # "import" | "manual"


class ETFPrice(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    position_id: int = Field(foreign_key="etfposition.id")
    date: date
    price_eur: float
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
