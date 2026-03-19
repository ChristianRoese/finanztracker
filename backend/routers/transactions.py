from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, text
from sqlmodel import Session, col, select

from backend.database import get_session
from backend.models.transaction import Transaction, TransactionUpdate, CATEGORIES

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("")
def list_transactions(
    session: Annotated[Session, Depends(get_session)],
    month: Optional[str] = Query(None, description="z.B. '2026-01'"),
    category: Optional[str] = Query(None),
    limit: int = Query(200, le=1000),
    offset: int = 0,
):
    q = select(Transaction)
    if month:
        q = q.where(Transaction.month == month)
    if category:
        q = q.where(Transaction.category == category)
    q = q.order_by(col(Transaction.date).desc()).offset(offset).limit(limit)
    return session.exec(q).all()


@router.put("/{tx_id}/category")
def update_category(
    tx_id: int,
    update: TransactionUpdate,
    session: Annotated[Session, Depends(get_session)],
):
    tx = session.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(404, "Transaktion nicht gefunden")
    if update.category not in CATEGORIES:
        raise HTTPException(400, f"Ungültige Kategorie: {update.category}")
    tx.category = update.category
    tx.category_source = "manual"
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


@router.get("/summary")
def monthly_summary(session: Annotated[Session, Depends(get_session)]):
    """Monatliche Ein-/Ausgaben-Zusammenfassung via SQL-Aggregation."""
    rows = session.exec(
        select(
            Transaction.month,
            func.sum(case((Transaction.amount > 0, Transaction.amount), else_=0.0)).label("income"),
            func.sum(case((Transaction.amount < 0, Transaction.amount), else_=0.0)).label("expenses_neg"),
            func.count(Transaction.id).label("tx_count"),
        )
        .group_by(Transaction.month)
        .order_by(col(Transaction.month))
    ).all()
    return [
        {
            "month": row.month,
            "income": round(row.income or 0.0, 2),
            "expenses": round(abs(row.expenses_neg or 0.0), 2),
            "net": round((row.income or 0.0) + (row.expenses_neg or 0.0), 2),
            "tx_count": row.tx_count,
        }
        for row in rows
    ]


@router.get("/categories")
def category_breakdown(
    session: Annotated[Session, Depends(get_session)],
    month: Optional[str] = Query(None),
):
    """Ausgaben pro Kategorie via SQL-Aggregation (optional gefiltert nach Monat)."""
    q = select(Transaction.category, func.sum(Transaction.amount).label("total_neg")).where(
        Transaction.amount < 0
    )
    if month:
        q = q.where(Transaction.month == month)
    q = q.group_by(Transaction.category).order_by(text("total_neg"))

    rows = session.exec(q).all()
    return [
        {"category": row.category, "total": round(abs(row.total_neg or 0.0), 2)}
        for row in rows
    ]


@router.get("/months")
def available_months(session: Annotated[Session, Depends(get_session)]):
    """Alle Monate für die Transaktionen vorhanden sind."""
    rows = session.exec(
        select(Transaction.month).distinct().order_by(col(Transaction.month).desc())
    ).all()
    return list(rows)


@router.get("/categories/list")
def categories_list():
    return CATEGORIES
