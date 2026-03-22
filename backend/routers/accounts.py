"""
Accounts-Router: Bankkonto-Verwaltung.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import Session, col, select

from backend.database import get_session
from backend.models.account import BankAccount, BankAccountUpdate
from backend.models.transaction import Transaction

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("")
def list_accounts(session: SessionDep) -> list[dict]:
    """Alle Bankkonten mit Buchungsstatistik."""
    accounts = session.exec(select(BankAccount).order_by(col(BankAccount.created_at))).all()
    result: list[dict] = []

    for acc in accounts:
        row = session.exec(
            select(
                func.count(Transaction.id).label("tx_count"),
                func.min(col(Transaction.date)).label("date_from"),
                func.max(col(Transaction.date)).label("date_to"),
            ).where(Transaction.account_id == acc.id)
        ).first()

        result.append({
            "id":         acc.id,
            "name":       acc.name,
            "iban":       acc.iban,
            "created_at": acc.created_at.isoformat(),
            "tx_count":   row.tx_count if row else 0,
            "date_from":  str(row.date_from) if row and row.date_from else None,
            "date_to":    str(row.date_to) if row and row.date_to else None,
        })

    return result


@router.put("/{account_id}")
def update_account(account_id: int, update: BankAccountUpdate, session: SessionDep) -> BankAccount:
    """Kontoname umbenennen."""
    account = session.get(BankAccount, account_id)
    if not account:
        raise HTTPException(404, "Konto nicht gefunden")
    account.name = update.name
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


@router.delete("/{account_id}")
def delete_account(account_id: int, session: SessionDep) -> dict:
    """Konto und alle zugehörigen Transaktionen löschen."""
    account = session.get(BankAccount, account_id)
    if not account:
        raise HTTPException(404, "Konto nicht gefunden")

    txs = session.exec(
        select(Transaction).where(Transaction.account_id == account_id)
    ).all()
    tx_count = len(txs)
    for tx in txs:
        session.delete(tx)

    session.delete(account)
    session.commit()
    return {"deleted_transactions": tx_count, "account_name": account.name}
