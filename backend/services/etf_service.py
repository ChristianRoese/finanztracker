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

# Szenarien für 5-Jahres-Prognose (jährliche Wachstumsrate)
FORECAST_SCENARIOS: dict[str, float] = {
    "best":    0.10,   # 10 % p.a.
    "casual":  0.07,   # 7 % p.a. (historischer Marktdurchschnitt)
    "worst":   0.03,   # 3 % p.a.
}
FORECAST_YEARS = 5


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


def _calc_cagr(total_invested: float, current_value: float, first_purchase_date: date) -> float | None:
    """Jährliche CAGR-Rendite in Prozent. None wenn Haltedauer < 30 Tage."""
    years_held = (date.today() - first_purchase_date).days / 365.25
    if years_held < 0.08 or total_invested <= 0:  # < ~30 Tage
        return None
    try:
        cagr = ((current_value / total_invested) ** (1.0 / years_held) - 1.0) * 100
        return round(cagr, 2)
    except (ZeroDivisionError, ValueError):
        return None


def _calc_forecast(current_value: float, monthly_amount: float) -> dict[str, list[float]]:
    """
    5-Jahres-Prognose mit monatlichen Einzahlungen (Compound Monthly Growth).
    Formel: V_n = V_0 * (1+r_m)^n + PMT * ((1+r_m)^n - 1) / r_m
    Gibt Jahreswerte 1–5 pro Szenario zurück.
    """
    scenarios: dict[str, list[float]] = {}
    for label, annual_rate in FORECAST_SCENARIOS.items():
        monthly_rate = (1 + annual_rate) ** (1 / 12) - 1
        value = current_value
        yearly_values: list[float] = []
        for _year in range(FORECAST_YEARS):
            for _month in range(12):
                value = value * (1 + monthly_rate) + monthly_amount
            yearly_values.append(round(value, 2))
        scenarios[label] = yearly_values
    return scenarios


def get_portfolio_summary(session: Session) -> list[dict]:
    """Performance-Zusammenfassung aller Positionen inkl. CAGR."""
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

        first_purchase_date = min(p.date for p in purchases)
        years_held = round((date.today() - first_purchase_date).days / 365.25, 2)
        cagr = _calc_cagr(total_invested, current_value, first_purchase_date)

        result.append({
            "isin":                pos.isin,
            "wkn":                 pos.wkn,
            "name":                pos.name,
            "ticker":              pos.ticker,
            "monthly_amount":      pos.monthly_amount,
            "total_invested":      round(total_invested, 2),
            "total_shares":        round(total_shares, 4),
            "avg_buy_price":       round(avg_price, 4),
            "current_price":       round(current_price, 4),
            "current_value":       round(current_value, 2),
            "gain_eur":            round(gain_eur, 2),
            "gain_pct":            round(gain_pct, 2),
            "yearly_return_cagr":  cagr,
            "years_held":          years_held,
            "first_purchase_date": first_purchase_date.isoformat(),
            "purchase_count":      len(purchases),
            "price_updated":       latest_price_entry.fetched_at.isoformat() if latest_price_entry else None,
        })

    return result


def get_etf_forecast(session: Session) -> dict:
    """
    5-Jahres-Prognose für alle Positionen (Best/Casual/Worst).
    Gibt Jahreswerte 1–5 pro Szenario zurück, sowohl je Position als auch aggregiert.
    """
    positions = session.exec(select(ETFPosition)).all()
    position_forecasts: list[dict] = []

    # Aggregierte Startwerte über alle Positionen
    total_current_value = 0.0
    total_monthly = 0.0

    for pos in positions:
        purchases = session.exec(
            select(ETFPurchase).where(ETFPurchase.position_id == pos.id)
        ).all()
        if not purchases:
            continue

        total_shares = sum(p.shares for p in purchases)
        latest_price_entry = session.exec(
            select(ETFPrice)
            .where(ETFPrice.position_id == pos.id)
            .order_by(col(ETFPrice.date).desc())
        ).first()
        avg_price = sum(p.total_eur for p in purchases) / total_shares if total_shares else 0.0
        current_price = latest_price_entry.price_eur if latest_price_entry else avg_price
        current_value = total_shares * current_price

        total_current_value += current_value
        total_monthly += pos.monthly_amount

        position_forecasts.append({
            "isin":     pos.isin,
            "name":     pos.name,
            "current_value": round(current_value, 2),
            "monthly_amount": pos.monthly_amount,
            "scenarios": _calc_forecast(current_value, pos.monthly_amount),
        })

    aggregate = {
        "current_value":  round(total_current_value, 2),
        "monthly_amount": round(total_monthly, 2),
        "scenarios":      _calc_forecast(total_current_value, total_monthly),
    }

    return {
        "positions":  position_forecasts,
        "aggregate":  aggregate,
        "years":      list(range(1, FORECAST_YEARS + 1)),
        "scenario_rates": {k: int(v * 100) for k, v in FORECAST_SCENARIOS.items()},
    }
