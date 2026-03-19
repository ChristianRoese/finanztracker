"""
ETF-Service: Preise via yfinance fetchen.
ISIN → Ticker-Mapping für die bekannten Positionen.
"""

import logging
from datetime import date

import yfinance as yf
from sqlmodel import Session, col, select

from backend.models.etf import ETFPosition, ETFPrice, ETFPurchase

logger = logging.getLogger(__name__)

# Bekannte ISIN → yfinance Ticker Mappings
ISIN_TO_TICKER: dict[str, str] = {
    "IE00BK1PV551": "XDWD.DE",   # Xtrackers MSCI World 1D
    "IE00B3YLTY66": "SPYW.DE",   # SPDR MSCI ACWI IMI
}


def get_or_create_position(session: Session, isin: str, wkn: str = "", name: str = "") -> ETFPosition:
    pos = session.exec(select(ETFPosition).where(ETFPosition.isin == isin)).first()
    if not pos:
        ticker = ISIN_TO_TICKER.get(isin, "")
        pos = ETFPosition(isin=isin, wkn=wkn, name=name or isin, ticker=ticker)
        session.add(pos)
        session.commit()
        session.refresh(pos)
    return pos


def fetch_current_price(ticker: str) -> float | None:
    """Aktuellen Preis via yfinance holen."""
    if not ticker:
        return None
    try:
        data = yf.Ticker(ticker)
        hist = data.history(period="5d")
        if hist.empty:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception as e:
        logger.error(f"yfinance Fehler für {ticker}: {e}")
        return None


def refresh_all_prices(session: Session) -> dict[str, float]:
    """Alle ETF-Positionen mit aktuellem Preis updaten. Upsert pro Tag."""
    positions = session.exec(select(ETFPosition)).all()
    updated: dict[str, float] = {}
    today = date.today()

    for pos in positions:
        if not pos.ticker:
            pos.ticker = ISIN_TO_TICKER.get(pos.isin, "")

        price = fetch_current_price(pos.ticker)
        if price is None:
            continue

        existing = session.exec(
            select(ETFPrice)
            .where(ETFPrice.position_id == pos.id)
            .where(ETFPrice.date == today)
        ).first()

        if existing:
            existing.price_eur = price
        else:
            session.add(ETFPrice(position_id=pos.id, date=today, price_eur=price))

        updated[pos.isin] = price

    session.commit()
    return updated


def get_portfolio_summary(session: Session) -> list[dict]:
    """Performance-Zusammenfassung aller Positionen."""
    positions = session.exec(select(ETFPosition)).all()
    result: list[dict] = []

    for pos in positions:
        purchases = session.exec(
            select(ETFPurchase).where(ETFPurchase.position_id == pos.id)
        ).all()

        if not purchases:
            continue

        total_invested = sum(p.total_eur for p in purchases)
        total_shares   = sum(p.shares for p in purchases)
        avg_price      = total_invested / total_shares if total_shares else 0.0

        # Letzter bekannter Preis
        latest_price_entry = session.exec(
            select(ETFPrice)
            .where(ETFPrice.position_id == pos.id)
            .order_by(col(ETFPrice.date).desc())
        ).first()

        current_price = latest_price_entry.price_eur if latest_price_entry else avg_price
        current_value = total_shares * current_price
        gain_eur      = current_value - total_invested
        gain_pct      = (gain_eur / total_invested * 100) if total_invested else 0.0

        result.append({
            "isin":            pos.isin,
            "wkn":             pos.wkn,
            "name":            pos.name,
            "ticker":          pos.ticker,
            "monthly_amount":  pos.monthly_amount,
            "total_invested":  round(total_invested, 2),
            "total_shares":    round(total_shares, 4),
            "avg_buy_price":   round(avg_price, 4),
            "current_price":   round(current_price, 4),
            "current_value":   round(current_value, 2),
            "gain_eur":        round(gain_eur, 2),
            "gain_pct":        round(gain_pct, 2),
            "purchase_count":  len(purchases),
            "price_updated":   latest_price_entry.fetched_at.isoformat() if latest_price_entry else None,
        })

    return result
