from datetime import date, datetime
from typing import Optional
from sqlmodel import Field, SQLModel

CATEGORIES = [
    "Lebensmittel",
    "Lieferando",
    "Restaurant/Café",
    "Amazon",
    "Streaming",
    "Gaming",
    "Versicherung",
    "Kredit & Schulden",
    "Investments",
    "Transport & Auto",
    "Gesundheit",
    "Sonstiges",
    "Einnahmen",
]


class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: date
    description: str
    merchant: str
    amount: float                          # negative = Ausgabe, positive = Einnahme
    category: str = "Sonstiges"
    category_source: str = "ai"           # "ai" | "manual" | "rule"
    account_statement: str = ""           # z.B. "2/2026"
    account_id: Optional[int] = Field(default=None, foreign_key="bankaccount.id")
    month: str = ""                       # "2026-01"
    import_hash: str = ""                 # SHA256 für Duplikat-Erkennung
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TransactionUpdate(SQLModel):
    category: str
