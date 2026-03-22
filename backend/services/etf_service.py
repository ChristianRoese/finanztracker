"""
ETF-Service: Preise via direkten Yahoo Finance HTTP-Request fetchen.
ISIN → Ticker-Mapping für die bekannten Positionen.
"""

import logging
import time
from datetime import date

import requests
from sqlmodel import Session, col, select

from backend.models.etf import ETFPosition, ETFPrice, ETFPurchase

logger = logging.getLogger(__name__)

# Alias-ISINs → kanonische ISIN (z.B. alte Fondsnummer → neue)
ISIN_ALIAS: dict[str, str] = {
    "IE00BJ0KDQ92": "IE00BK1PV551",   # Xtrackers MSCI World 1C → 1D (gleicher ETF, neue ISIN)
}

# Bekannte ISIN → yfinance Ticker Mappings
ISIN_TO_TICKER: dict[str, str] = {
    "IE00BK1PV551": "XDWD.DE",   # Xtrackers MSCI World 1D
    "IE00B3YLTY66": "SPYI.DE",   # SPDR MSCI ACWI IMI (nach Split/Umbenennung Feb 2026)
    "IE00BJ0KDQ92": "XDWD.DE",   # Xtrackers MSCI World 1C
    "IE000FPWSL69": "K0MR.DE",   # L&G Gerd Kommer Multifactor Equity
}

# Bekannte ISIN → lesbarer ETF-Name
ISIN_TO_NAME: dict[str, str] = {
    "IE00BK1PV551": "Xtrackers MSCI World 1D",
    "IE00B3YLTY66": "SPDR MSCI ACWI IMI",
    "IE00BJ0KDQ92": "Xtrackers MSCI World 1C",
    "IE000FPWSL69": "L&G Gerd Kommer Multifactor Equity",
    "IE00B4L5Y983": "iShares Core MSCI World",
}

# Szenarien für 5-Jahres-Prognose (jährliche Wachstumsrate)
FORECAST_SCENARIOS: dict[str, float] = {
    "best":    0.10,   # 10 % p.a.
    "casual":  0.07,   # 7 % p.a. (historischer Marktdurchschnitt)
    "worst":   0.03,   # 3 % p.a.
}
FORECAST_YEARS = 5


def get_or_create_position(session: Session, isin: str, wkn: str = "", name: str = "") -> ETFPosition:
    isin = ISIN_ALIAS.get(isin, isin)  # Alias auflösen
    pos = session.exec(select(ETFPosition).where(ETFPosition.isin == isin)).first()
    if not pos:
        ticker = ISIN_TO_TICKER.get(isin, "")
        resolved_name = ISIN_TO_NAME.get(isin) or name or isin
        pos = ETFPosition(isin=isin, wkn=wkn, name=resolved_name, ticker=ticker)
        session.add(pos)
        session.commit()
        session.refresh(pos)
    return pos


_YF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def _get_fx_rate(from_currency: str) -> float:
    """Wechselkurs from_currency → EUR via Yahoo Finance."""
    if from_currency == "EUR":
        return 1.0
    pair = f"{from_currency}EUR=X"
    try:
        resp = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{pair}?interval=1d&range=5d",
            headers=_YF_HEADERS, timeout=10,
        )
        resp.raise_for_status()
        closes = resp.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        rate = next((c for c in reversed(closes) if c is not None), None)
        return float(rate) if rate else 1.0
    except Exception as e:
        logger.error(f"FX-Kurs {from_currency}→EUR Fehler: {e}")
        return 1.0


def _fetch_price_yahoo(ticker: str) -> tuple[float, str] | tuple[None, None]:
    """Preis + Währung via Yahoo Finance Chart-API."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"
    try:
        resp = requests.get(url, headers=_YF_HEADERS, timeout=10)
        resp.raise_for_status()
        result = resp.json()["chart"]["result"][0]
        closes = result["indicators"]["quote"][0]["close"]
        price = next((c for c in reversed(closes) if c is not None), None)
        if price is None:
            return None, None
        currency = result["meta"].get("currency", "EUR").upper()
        # GBX = Pence → in GBP umrechnen
        if currency == "GBX":
            price = price / 100
            currency = "GBP"
        return float(price), currency
    except Exception as e:
        logger.error(f"Yahoo Finance Fehler für {ticker}: {e}")
        return None, None


def _resolve_ticker_from_isin(isin: str) -> str | None:
    """ISIN → Ticker via Yahoo Finance Search-API."""
    url = f"https://query1.finance.yahoo.com/v1/finance/search?q={isin}&quotesCount=10&newsCount=0&enableFuzzyQuery=false"
    try:
        resp = requests.get(url, headers=_YF_HEADERS, timeout=10)
        resp.raise_for_status()
        quotes = resp.json().get("quotes", [])
        # Bevorzuge EUR-Börsen (.DE zuerst), sonst ersten Treffer nehmen
        for suffix in (".DE", ".F", ".MU", ".PA", ".AS", ".MI"):
            for q in quotes:
                if q.get("symbol", "").endswith(suffix):
                    return q["symbol"]
        return quotes[0]["symbol"] if quotes else None
    except Exception as e:
        logger.error(f"Yahoo ISIN-Suche Fehler für {isin}: {e}")
        return None


def fetch_price_by_isin(isin: str, fallback_ticker: str = "") -> float | None:
    """Preis per ISIN via Yahoo Finance, immer in EUR zurückgeben."""
    # Ticker ermitteln: erst ISIN-Suche, dann Mapping, dann Fallback
    ticker = _resolve_ticker_from_isin(isin) or ISIN_TO_TICKER.get(isin) or fallback_ticker
    if not ticker:
        logger.error(f"Kein Ticker für ISIN {isin} gefunden")
        return None

    price, currency = _fetch_price_yahoo(ticker)
    if price is None:
        return None

    # In EUR umrechnen falls nötig
    if currency != "EUR":
        rate = _get_fx_rate(currency)
        price_eur = price * rate
        logger.info(f"{isin} via {ticker}: {price:.4f} {currency} × {rate:.4f} = {price_eur:.4f} EUR")
        return round(price_eur, 4)

    logger.info(f"{isin} via {ticker}: {price:.4f} EUR")
    return round(price, 4)


def refresh_all_prices(session: Session) -> dict[str, float]:
    """Alle ETF-Positionen mit aktuellem Preis updaten. Upsert pro Tag."""
    positions = session.exec(select(ETFPosition).where(ETFPosition.fully_sold == False)).all()
    updated: dict[str, float] = {}
    today = date.today()

    for pos in positions:
        price = fetch_price_by_isin(pos.isin, fallback_ticker=pos.ticker or ISIN_TO_TICKER.get(pos.isin, ""))
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


def _last_monthly_amount(buys: list[ETFPurchase]) -> float:
    """Sparplan-Betrag = Summe aller Käufe im letzten Kaufmonat."""
    if not buys:
        return 0.0
    latest_month = max(p.date.strftime("%Y-%m") for p in buys)
    month_total = sum(p.total_eur for p in buys if p.date.strftime("%Y-%m") == latest_month)
    return round(month_total, 2)


def get_portfolio_summary(session: Session) -> list[dict]:
    """Performance-Zusammenfassung aller aktiven Positionen inkl. CAGR."""
    positions = session.exec(select(ETFPosition).where(ETFPosition.fully_sold == False)).all()
    result: list[dict] = []

    for pos in positions:
        purchases = session.exec(
            select(ETFPurchase).where(ETFPurchase.position_id == pos.id)
        ).all()

        if not purchases:
            continue

        buys  = [p for p in purchases if (p.transaction_type or "buy") == "buy"]
        sells = [p for p in purchases if (p.transaction_type or "buy") == "sell"]

        bought_shares  = sum(p.shares for p in buys)
        sold_shares    = sum(p.shares for p in sells)
        total_shares   = bought_shares - sold_shares

        total_invested = sum(p.total_eur for p in buys) - sum(p.total_eur for p in sells)
        avg_price      = total_invested / total_shares if total_shares > 0 else 0.0

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

        fully_sold = total_shares <= 0.0001  # Toleranz für Rundungsfehler
        effective_monthly = 0.0 if fully_sold else (
            pos.monthly_amount if pos.monthly_amount > 0 else _last_monthly_amount(buys)
        )

        result.append({
            "isin":                pos.isin,
            "wkn":                 pos.wkn,
            "name":                pos.name,
            "ticker":              pos.ticker,
            "monthly_amount":      effective_monthly,
            "total_invested":      round(total_invested, 2),
            "total_shares":        round(max(total_shares, 0.0), 4),
            "avg_buy_price":       round(avg_price, 4),
            "current_price":       round(current_price, 4),
            "current_value":       round(current_value if not fully_sold else 0.0, 2),
            "gain_eur":            round(gain_eur if not fully_sold else 0.0, 2),
            "gain_pct":            round(gain_pct if not fully_sold else 0.0, 2),
            "yearly_return_cagr":  None if fully_sold else cagr,
            "years_held":          years_held,
            "first_purchase_date": first_purchase_date.isoformat(),
            "purchase_count":      len(buys),
            "sell_count":          len(sells),
            "fully_sold":          fully_sold,
            "price_updated":       latest_price_entry.fetched_at.isoformat() if latest_price_entry else None,
        })

    return result


def get_etf_forecast(session: Session) -> dict:
    """
    5-Jahres-Prognose für alle Positionen (Best/Casual/Worst).
    Gibt Jahreswerte 1–5 pro Szenario zurück, sowohl je Position als auch aggregiert.
    """
    positions = session.exec(select(ETFPosition).where(ETFPosition.fully_sold == False)).all()
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

        buys_f  = [p for p in purchases if (p.transaction_type or "buy") == "buy"]
        sells_f = [p for p in purchases if (p.transaction_type or "buy") == "sell"]
        total_shares = sum(p.shares for p in buys_f) - sum(p.shares for p in sells_f)

        if total_shares <= 0:
            continue  # Position vollständig verkauft → nicht in Prognose aufnehmen

        latest_price_entry = session.exec(
            select(ETFPrice)
            .where(ETFPrice.position_id == pos.id)
            .order_by(col(ETFPrice.date).desc())
        ).first()
        buy_total = sum(p.total_eur for p in buys_f) - sum(p.total_eur for p in sells_f)
        avg_price = buy_total / total_shares if total_shares else 0.0
        current_price = latest_price_entry.price_eur if latest_price_entry else avg_price
        current_value = total_shares * current_price

        effective_monthly = pos.monthly_amount if pos.monthly_amount > 0 else _last_monthly_amount(buys_f)

        total_current_value += current_value
        total_monthly += effective_monthly

        position_forecasts.append({
            "isin":     pos.isin,
            "name":     pos.name,
            "current_value": round(current_value, 2),
            "monthly_amount": effective_monthly,
            "scenarios": _calc_forecast(current_value, effective_monthly),
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
