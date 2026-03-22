"""
Import-Router: PDF hochladen → parsen → kategorisieren → speichern.
"""

import io
import re
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlmodel import Session, select, col, func

from backend.database import get_session
from backend.models.account import BankAccount
from backend.models.transaction import Transaction
from backend.models.etf import ETFPosition, ETFPurchase
from backend.services.categorizer import categorize_batch
from backend.services.etf_service import get_or_create_position
from backend.services.pdf_parser import parse_pdf

router = APIRouter(prefix="/api/import", tags=["import"])

STATEMENT_RE = re.compile(r"(\d+)/(\d{4})")


def _extract_statement_label(filename: str) -> str:
    m = STATEMENT_RE.search(filename)
    return m.group(0) if m else filename[:20]


def _get_or_create_account(session: Session, iban: str, account_name: str) -> BankAccount | None:
    """Findet Konto per IBAN oder legt es neu an. Gibt None zurück wenn keine Infos vorhanden."""
    if not iban and not account_name:
        return None

    if iban:
        existing = session.exec(
            select(BankAccount).where(BankAccount.iban == iban)
        ).first()
        if existing:
            return existing

    name = account_name.strip() if account_name.strip() else (iban or "Unbekanntes Konto")
    account = BankAccount(name=name, iban=iban)
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


@router.post("/pdf")
async def import_pdf(
    file: UploadFile,
    session: Annotated[Session, Depends(get_session)],
    account_name: str = Form(""),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Nur PDF-Dateien erlaubt")

    content = await file.read()
    statement_label = _extract_statement_label(file.filename)

    # Parsen
    try:
        parsed, iban = parse_pdf(io.BytesIO(content), statement_label)
    except Exception as e:
        import traceback, logging
        logging.getLogger(__name__).error("PDF parse error: %s\n%s", e, traceback.format_exc())
        raise HTTPException(422, f"PDF konnte nicht geparst werden: {e}")

    if not parsed:
        raise HTTPException(422, "Keine Transaktionen im PDF gefunden")

    # Konto anlegen/finden
    account = _get_or_create_account(session, iban, account_name)
    account_id = account.id if account else None

    # Duplikate filtern
    existing_hashes = set(
        session.exec(select(Transaction.import_hash)).all()
    )
    new_txs = [p for p in parsed if p.import_hash not in existing_hashes]

    if not new_txs:
        return {
            "imported": 0,
            "skipped": len(parsed),
            "message": "Alle Buchungen bereits vorhanden",
            "account_id": account_id,
            "account_name": account.name if account else None,
            "iban": iban or None,
        }

    # Kategorisieren (nur Nicht-ETF- und Nicht-Dividenden-Transaktionen)
    non_etf = [t for t in new_txs if not t.is_etf and not t.is_dividend]
    cat_items = [
        {"id": t.import_hash, "merchant": t.merchant, "description": t.description, "amount": t.amount}
        for t in non_etf
    ]
    # id → category mapping (key = import_hash)
    categories = categorize_batch(cat_items) if cat_items else {}

    imported_tx   = 0
    imported_etf  = 0
    skipped       = len(parsed) - len(new_txs)

    for p in new_txs:
        month_str = f"{p.date.year}-{p.date.month:02d}"

        if p.is_dividend:
            # Dividende → als Einnahme buchen, kein ETF-Kauf
            category = "Einnahmen"
            cat_source = "rule"
        elif p.is_etf and p.etf_isin:
            # ETF-Kauf (amount < 0) oder Verkauf (amount > 0)
            is_sale = p.amount > 0
            pos = get_or_create_position(
                session, p.etf_isin, p.etf_wkn or "", p.description[:60]
            )
            if p.etf_shares and p.etf_price:
                purchase = ETFPurchase(
                    position_id=pos.id,
                    date=p.date,
                    price_eur=p.etf_price,
                    shares=p.etf_shares,
                    total_eur=abs(p.amount),
                    source="import",
                    transaction_type="sell" if is_sale else "buy",
                )
                session.add(purchase)
                imported_etf += 1

            # Auch als Transaktion speichern (für Ausgabenübersicht)
            category = "Investments"
            cat_source = "rule"
        else:
            category = categories.get(p.import_hash, "Sonstiges")
            cat_source = "ai" if p.import_hash in categories else "rule"

        tx = Transaction(
            date=p.date,
            description=p.description,
            merchant=p.merchant,
            amount=p.amount,
            category=category,
            category_source=cat_source,
            account_statement=statement_label,
            account_id=account_id,
            month=month_str,
            import_hash=p.import_hash,
        )
        session.add(tx)
        imported_tx += 1

    session.commit()

    # Nach Import: fully_sold automatisch setzen wenn Net-Shares <= 0
    positions = session.exec(select(ETFPosition)).all()
    for pos in positions:
        purchases = session.exec(
            select(ETFPurchase).where(ETFPurchase.position_id == pos.id)
        ).all()
        if purchases:
            net = sum(
                p.shares if p.transaction_type == "buy" else -p.shares
                for p in purchases
            )
            should_be_sold = net <= 0.001
            if pos.fully_sold != should_be_sold:
                pos.fully_sold = should_be_sold
                session.add(pos)
    session.commit()

    return {
        "imported": imported_tx,
        "imported_etf_purchases": imported_etf,
        "skipped": skipped,
        "total_in_pdf": len(parsed),
        "statement": statement_label,
        "account_id": account_id,
        "account_name": account.name if account else None,
        "iban": iban or None,
    }


@router.get("/statements")
def list_statements(session: Annotated[Session, Depends(get_session)]):
    """Alle importierten Auszüge mit Buchungsanzahl und Zeitraum."""
    rows = session.exec(
        select(
            col(Transaction.account_statement),
            func.count().label("tx_count"),
            func.min(col(Transaction.date)).label("date_from"),
            func.max(col(Transaction.date)).label("date_to"),
            func.sum(func.iif(col(Transaction.amount) < 0, col(Transaction.amount), 0)).label("expenses"),
            func.sum(func.iif(col(Transaction.amount) > 0, col(Transaction.amount), 0)).label("income"),
        )
        .group_by(col(Transaction.account_statement))
        .order_by(func.min(col(Transaction.date)).desc())
    ).all()
    return [
        {
            "statement": r[0],
            "tx_count": r[1],
            "date_from": str(r[2]),
            "date_to": str(r[3]),
            "expenses": round(abs(r[4] or 0), 2),
            "income": round(r[5] or 0, 2),
        }
        for r in rows
    ]


@router.delete("/statements")
def delete_statement(statement: str, session: Annotated[Session, Depends(get_session)]):
    """Löscht alle Transaktionen eines Auszugs (statement als Query-Parameter)."""
    txs = session.exec(
        select(Transaction).where(col(Transaction.account_statement) == statement)
    ).all()
    if not txs:
        raise HTTPException(404, f"Auszug '{statement}' nicht gefunden")
    count = len(txs)
    for tx in txs:
        session.delete(tx)
    session.commit()
    return {"deleted": count, "statement": statement}
