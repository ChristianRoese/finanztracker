"""
DKB Kontoauszug PDF-Parser.

DKB-PDFs haben eine konsistente Tabellenstruktur:
  Datum | Erläuterung | Betrag Soll EUR | Betrag Haben EUR

Besonderheiten:
- Kontostand-Zeilen überspringen (kein Datum, Text enthält "Kontostand")
- Deutsches Zahlenformat: 1.234,56 → float
- Wertpapierabrechnungen separat als ETF-Käufe extrahieren
- Mehrzeilige Erläuterungen zusammenführen
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from typing import BinaryIO, Optional

import pdfplumber


DATE_PATTERN = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
AMOUNT_PATTERN = re.compile(r"^-?\d{1,3}(?:\.\d{3})*,\d{2}$")
ETF_KEYWORDS = ("Wertpapierabrechnung", "Wertp.Abrechn.", "Wertpapierertrag")
SKIP_KEYWORDS = ("Kontostand", "Dispositionskredit", "Gesamtumsatz", "Hinweise", "Summe Soll")


@dataclass
class ParsedTransaction:
    date: date
    description: str
    merchant: str
    amount: float
    is_etf: bool = False
    etf_isin: Optional[str] = None
    etf_wkn: Optional[str] = None
    etf_shares: Optional[float] = None
    etf_price: Optional[float] = None
    import_hash: str = ""
    account_statement: str = ""


def _parse_amount(raw: str) -> Optional[float]:
    """'1.234,56' → 1234.56 | '-250,00' → -250.0"""
    if not raw or not raw.strip():
        return None
    cleaned = raw.strip().replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_date(raw: str) -> Optional[date]:
    """'05.01.2026' → date(2026, 1, 5)"""
    if not raw or not DATE_PATTERN.match(raw.strip()):
        return None
    try:
        d, m, y = raw.strip().split(".")
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def _clean_merchant(description: str) -> str:
    """Extrahiert lesbaren Händlernamen aus DKB-Beschreibungstext."""
    # Erste Zeile / bis zum ersten Zeilenumbruch oder Slash
    first = description.split("/")[0].split("\n")[0].strip()
    # Bekannte Präfixe entfernen
    for prefix in ("Kartenzahlung", "Kartenzahlung onl", "Basislastschrift",
                    "Zahlungseingang", "Dauerauftrag", "Überweisung",
                    "Lohn, Gehalt, Rente", "sonstige Entgelte",
                    "Wertpapierabrechnung", "Verfügung Geldautomat"):
        if first.lower().startswith(prefix.lower()):
            first = first[len(prefix):].strip(" .,/")
    return first[:80] if first else description[:80]


def _extract_etf_meta(description: str) -> dict:
    """Extrahiert ISIN, WKN, Stück und Preis aus Wertpapierabrechnungstext."""
    meta: dict = {}
    isin_match = re.search(r"ISIN\s+([A-Z]{2}[A-Z0-9]{10})", description)
    wkn_match  = re.search(r"WKN\s+([A-Z0-9]{6})", description)
    shares_match = re.search(r"Stück\s+([\d,]+)", description)
    price_match  = re.search(r"Preis\s+([\d.,]+)\s*EUR", description)

    if isin_match:  meta["isin"]   = isin_match.group(1)
    if wkn_match:   meta["wkn"]    = wkn_match.group(1)
    if shares_match:
        meta["shares"] = _parse_amount(shares_match.group(1)) or 0.0
    if price_match:
        meta["price"]  = _parse_amount(price_match.group(1)) or 0.0
    return meta


def _make_hash(tx_date: date, description: str, amount: float, statement_label: str = "") -> str:
    key = f"{statement_label}|{tx_date}|{description[:60]}|{amount:.2f}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _should_skip(row: list) -> bool:
    text = " ".join(str(c) for c in row if c)
    return any(kw in text for kw in SKIP_KEYWORDS)


def parse_pdf(file: BinaryIO, statement_label: str = "") -> list[ParsedTransaction]:
    """
    Hauptfunktion: PDF-Bytes → Liste ParsedTransaction.
    statement_label: z.B. "2/2026" für Buchungsreferenz.
    """
    results: list[ParsedTransaction] = []

    with pdfplumber.open(file) as pdf:
        raw_rows: list[list] = []

        for page in pdf.pages:
            table = page.extract_table({
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
            })
            if not table:
                # Fallback: text-basiertes Parsing
                table = page.extract_table()
            if table:
                raw_rows.extend(table)

        # Zusammenführen von mehrzeiligen Einträgen
        merged: list[list] = []
        for row in raw_rows:
            if not row or all(c is None or str(c).strip() == "" for c in row):
                continue
            if _should_skip(row):
                continue

            col0 = str(row[0] or "").strip()
            parsed_date = _parse_date(col0)

            if parsed_date:
                merged.append(list(row))
            elif merged:
                # Fortsetzungszeile → Beschreibung anhängen
                desc_part = " ".join(str(c) for c in row if c and str(c).strip())
                if desc_part and len(merged[-1]) > 1:
                    merged[-1][1] = (str(merged[-1][1] or "") + " " + desc_part).strip()

        # Parsen der zusammengeführten Zeilen
        for row in merged:
            if len(row) < 3:
                continue

            tx_date = _parse_date(str(row[0] or "").strip())
            if not tx_date:
                continue

            description = str(row[1] or "").strip()
            if not description:
                continue

            # Betrag: Soll (negativ) oder Haben (positiv)
            soll  = _parse_amount(str(row[2] or ""))
            haben = _parse_amount(str(row[3] or "")) if len(row) > 3 else None

            if soll is not None:
                amount = -abs(soll)
            elif haben is not None:
                amount = abs(haben)
            else:
                continue  # Kontostand-Zeile o.ä.

            is_etf = any(kw in description for kw in ETF_KEYWORDS)
            etf_meta = _extract_etf_meta(description) if is_etf else {}

            tx = ParsedTransaction(
                date=tx_date,
                description=description,
                merchant=_clean_merchant(description),
                amount=amount,
                is_etf=is_etf,
                etf_isin=etf_meta.get("isin"),
                etf_wkn=etf_meta.get("wkn"),
                etf_shares=etf_meta.get("shares"),
                etf_price=etf_meta.get("price"),
                import_hash=_make_hash(tx_date, description, amount, statement_label),
                account_statement=statement_label,
            )
            results.append(tx)

    return results
