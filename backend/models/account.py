from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class BankAccount(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str                          # Alias: "Girokonto", "Tagesgeld" etc.
    iban: str = ""                     # DE-IBAN aus PDF extrahiert
    created_at: datetime = Field(default_factory=datetime.utcnow)


class BankAccountUpdate(SQLModel):
    name: str
