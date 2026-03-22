from typing import Annotated, Optional
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlmodel import Session, select

from backend.database import get_session
from backend.models.transaction import Transaction

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/monthly/{year}/{month}")
def monthly_report(
    year: int,
    month: int,
    session: Annotated[Session, Depends(get_session)],
    account_id: Optional[int] = Query(None),
):
    month_str = f"{year}-{month:02d}"
    q = select(Transaction).where(Transaction.month == month_str)
    if account_id is not None:
        q = q.where(Transaction.account_id == account_id)
    txs = session.exec(q).all()

    if not txs:
        return {"month": month_str, "income": 0.0, "expenses": 0.0, "net": 0.0, "savings_rate": 0.0, "categories": []}

    income = sum(tx.amount for tx in txs if tx.amount > 0)
    expenses = sum(abs(tx.amount) for tx in txs if tx.amount < 0)
    net = income - expenses
    savings_rate = round((net / income * 100), 2) if income > 0 else 0.0

    cat_totals: dict[str, float] = defaultdict(float)
    for tx in txs:
        if tx.amount < 0:
            cat_totals[tx.category] += abs(tx.amount)

    categories = [
        {"category": k, "total": round(v, 2)}
        for k, v in sorted(cat_totals.items(), key=lambda x: -x[1])
    ]

    return {
        "month": month_str,
        "income": round(income, 2),
        "expenses": round(expenses, 2),
        "net": round(net, 2),
        "savings_rate": savings_rate,
        "categories": categories,
    }


@router.get("/trends")
def category_trends(
    session: Annotated[Session, Depends(get_session)],
    months: int = Query(12, ge=1, le=36),
    account_id: Optional[int] = Query(None),
    year: Optional[str] = Query(None),
):
    """Kategorien-Ausgaben über die letzten N Monate oder ein bestimmtes Jahr."""
    if year:
        month_list = [f"{year}-{mo:02d}" for mo in range(1, 13)]
    else:
        today = date.today()
        month_list: list[str] = []
        y, m = today.year, today.month
        for _ in range(months):
            month_list.append(f"{y}-{m:02d}")
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        month_list.reverse()

    q = select(Transaction.month, Transaction.category, func.sum(func.abs(Transaction.amount))).where(
        Transaction.month.in_(month_list),
        Transaction.amount < 0,
        Transaction.category != "Einnahmen",
    )
    if account_id is not None:
        q = q.where(Transaction.account_id == account_id)
    q = q.group_by(Transaction.month, Transaction.category)
    rows = session.exec(q).all()

    data: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for month_val, category, total in rows:
        data[category][month_val] = total

    series = [
        {
            "category": cat,
            "values": [round(data[cat].get(mo, 0.0), 2) for mo in month_list],
        }
        for cat in sorted(data.keys())
    ]

    return {"months": month_list, "series": series}
