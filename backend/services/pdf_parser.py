"""
DKB Kontoauszug PDF-Parser.

DKB-PDFs (aktuelles Format) liefern pro Seite eine zusammengefasste Tabellenzelle
mit allen Transaktionen. Der zuverlässigste Ansatz ist daher text-basiertes Parsing:

Format im Rohtext:
  DD.MM.YYYYBeschreibung                        -Betrag
  Folgezeile 1
  Folgezeile 2
  DD.MM.YYYYNächste Transaktion                  Betrag

Besonderheiten:
- Datum und Beschreibung ohne Leerzeichen zusammengeklebt
- Beträge am Zeilenende (deutsch: 1.234,56)
- Kontostand-Zeilen überspringen
- Wertpapierabrechnungen als ETF-Käufe extrahieren
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from typing import BinaryIO, Optional

import pdfplumber


# DD.MM.YYYY direkt gefolgt von Nicht-Leerzeichen (so klebt DKB Datum+Beschreibung zusammen)
TX_LINE_RE = re.compile(r"^(\d{2}\.\d{2}\.\d{4})(\S.*?)(?:\s{2,}|\s+(-?\d{1,3}(?:\.\d{3})*,\d{2}))?$")

# pdfplumber spaltet manchmal Datumszeilen: "3 0.12.2025..." statt "30.12.2025..."
SPLIT_DATE_RE = re.compile(r"^(\d) (\d\.\d{2}\.\d{4})")

# Fußzeilen-/Kopfzeilen-Muster die aus Beschreibungen entfernt werden müssen
# DKB hängt bei Seitenumbrüchen Impressum + nächste Seiten-Kopfzeile an Beschreibungen
FOOTER_PATTERNS: list[re.Pattern] = [
    re.compile(r"Deutsche Kreditbank AG.*?(?=\d{2}\.\d{2}\.\d{4}[A-ZÜÄÖ]|\Z)", re.DOTALL),
    re.compile(r"Kontoauszug\s+\d+/\d+\s+Seite\s+\d+\s+von\s+\d+.*?(?=\d{2}\.\d{2}\.\d{4}[A-ZÜÄÖ]|\Z)", re.DOTALL),
    re.compile(r"Girokonto\s+\d+,\s+DE\d+.*?(?=\d{2}\.\d{2}\.\d{4}[A-ZÜÄÖ]|\Z)", re.DOTALL),
    re.compile(r"Datum\s+Erläuterung\s+Betrag Soll EUR\s+Betrag Haben EUR"),
]
DATE_RE    = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
AMOUNT_RE  = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d{2}")
# IBAN-Muster: DE + 2 Prüfziffern + 18 Ziffern (ggf. mit Leerzeichen)
IBAN_RE    = re.compile(r"DE\d{2}[\s\d]{15,25}")

ETF_KEYWORDS      = ("Wertpapierabrechnung", "Wertp.Abrechn.")
DIVIDEND_KEYWORDS = ("Wertpapierertrag",)
SKIP_KEYWORDS     = ("Kontostand", "Dispositionskredit", "Gesamtumsatz",
                     "Hinweise", "Summe Soll", "Summe Haben", "Auszug Nr.")


@dataclass
class ParsedTransaction:
    date: date
    description: str
    merchant: str
    amount: float
    is_etf: bool = False
    is_dividend: bool = False
    etf_isin: Optional[str] = None
    etf_wkn: Optional[str] = None
    etf_shares: Optional[float] = None
    etf_price: Optional[float] = None
    import_hash: str = ""
    account_statement: str = ""


def _parse_amount(raw: str) -> Optional[float]:
    if not raw or not raw.strip():
        return None
    cleaned = raw.strip().replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_date(raw: str) -> Optional[date]:
    if not raw or not DATE_RE.match(raw.strip()):
        return None
    try:
        d, m, y = raw.strip().split(".")
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def _clean_merchant(description: str) -> str:
    first = description.split("/")[0].split("\n")[0].strip()
    for prefix in ("Kartenzahlung onl", "Kartenzahlung", "Basislastschrift",
                   "Zahlungseingang", "Dauerauftrag", "Überweisung",
                   "Lohn, Gehalt, Rente", "sonstige Entgelte",
                   "Wertpapierabrechnung", "Verfügung Geldautomat"):
        if first.lower().startswith(prefix.lower()):
            first = first[len(prefix):].strip(" .,/")
    return first[:80] if first else description[:80]


def _extract_etf_meta(description: str) -> dict:
    meta: dict = {}
    isin_match   = re.search(r"ISIN[:\s]+([A-Z]{2}[A-Z0-9]{10})", description)
    wkn_match    = re.search(r"WKN[:\s]+([A-Z0-9]{6})", description)
    shares_match = re.search(r"Stück[:\s]+([\d,.]+)", description)
    price_match  = re.search(r"(?:Preis|Kurs)\s+([\d.,]+)\s*EUR", description)
    if isin_match:   meta["isin"]   = isin_match.group(1)
    if wkn_match:    meta["wkn"]    = wkn_match.group(1)
    if shares_match: meta["shares"] = _parse_amount(shares_match.group(1)) or 0.0
    if price_match:  meta["price"]  = _parse_amount(price_match.group(1)) or 0.0
    return meta


def _make_hash(tx_date: date, description: str, amount: float, statement_label: str = "") -> str:
    key = f"{statement_label}|{tx_date}|{description[:60]}|{amount:.2f}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def extract_iban(raw_text: str) -> str:
    """Extrahiert die erste DE-IBAN aus dem PDF-Rohtext (vor Footer-Stripping)."""
    match = IBAN_RE.search(raw_text)
    if not match:
        return ""
    return re.sub(r"\s+", "", match.group(0))  # Leerzeichen entfernen → "DE12345..."


def _should_skip(text: str) -> bool:
    return any(kw in text for kw in SKIP_KEYWORDS)


def _find_amount_in_line(line: str) -> Optional[float]:
    """Sucht den letzten Betrag in einer Zeile (ganz rechts)."""
    matches = AMOUNT_RE.findall(line)
    if matches:
        return _parse_amount(matches[-1])
    return None


def _strip_footers(text: str) -> str:
    """Entfernt DKB-Fußzeilen und Seitenköpfe aus dem Volltext."""
    for pattern in FOOTER_PATTERNS:
        text = pattern.sub(" ", text)
    return text


def _parse_text(full_text: str) -> list[dict]:
    """
    Parst den Rohtext eines DKB-Kontoauszugs.

    Transaktionszeilen: DD.MM.YYYYBeschreibung ... Betrag
    Folgezeilen gehören zur letzten Transaktion.
    """
    raw_entries: list[dict] = []
    current: Optional[dict] = None

    for raw_line in full_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Split-Datum reparieren: "3 0.12.2025..." → "30.12.2025..."
        line = SPLIT_DATE_RE.sub(r"\1\2", line)

        # Prüfen ob Zeile mit DD.MM.YYYY beginnt (= neue Transaktion)
        if len(line) >= 10 and DATE_RE.match(line[:10]):
            # Vorherige Transaktion speichern
            if current is not None:
                raw_entries.append(current)

            tx_date_raw = line[:10]
            rest = line[10:]  # Beschreibung + evtl. Betrag

            tx_date = _parse_date(tx_date_raw)
            if tx_date is None:
                current = None
                continue

            # Betrag extrahieren (letztes Zahlenfeld in der Zeile)
            amount = _find_amount_in_line(rest)

            # Beschreibung: alles außer dem Betrag am Ende
            description = rest
            if amount is not None:
                # Betrag am Ende der Zeile entfernen
                description = AMOUNT_RE.sub("", rest).strip().rstrip("-").strip()

            current = {
                "date": tx_date,
                "description": description,
                "amount": amount,
            }

        elif current is not None:
            # Kontostand- und andere Skip-Zeilen nicht an Beschreibung hängen
            if _should_skip(line):
                continue

            # Folgezeile → an Beschreibung anhängen, Betrag nachziehen falls noch fehlend
            if current["amount"] is None:
                amt = _find_amount_in_line(line)
                if amt is not None:
                    current["amount"] = amt
                    # Betrag aus Zeile entfernen
                    line_clean = AMOUNT_RE.sub("", line).strip().rstrip("-").strip()
                    if line_clean:
                        current["description"] = (current["description"] + " " + line_clean).strip()
                    continue

            current["description"] = (current["description"] + " " + line).strip()

    if current is not None:
        raw_entries.append(current)

    return raw_entries


def parse_pdf(file: BinaryIO, statement_label: str = "") -> tuple[list[ParsedTransaction], str]:
    """PDF-Bytes → (Liste ParsedTransaction, IBAN oder '')."""
    results: list[ParsedTransaction] = []

    with pdfplumber.open(file) as pdf:
        # Gesamttext aller Seiten zusammensetzen
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            full_text += text + "\n"

        iban = extract_iban(full_text)
        raw_entries = _parse_text(_strip_footers(full_text))

        for entry in raw_entries:
            if _should_skip(entry["description"]):
                continue
            if entry["amount"] is None or entry["amount"] == 0.0:
                continue

            tx_date = entry["date"]
            description = entry["description"]
            amount = entry["amount"]

            # Betrag-Vorzeichen: DKB schreibt Soll bereits negativ, Haben positiv
            # Sicherheitshalber: Soll-Buchungen sind negativ
            is_etf     = any(kw in description for kw in ETF_KEYWORDS)
            is_dividend = any(kw in description for kw in DIVIDEND_KEYWORDS)
            etf_meta = _extract_etf_meta(description) if is_etf else {}

            tx = ParsedTransaction(
                date=tx_date,
                description=description,
                merchant=_clean_merchant(description),
                amount=amount,
                is_etf=is_etf,
                is_dividend=is_dividend,
                etf_isin=etf_meta.get("isin"),
                etf_wkn=etf_meta.get("wkn"),
                etf_shares=etf_meta.get("shares"),
                etf_price=etf_meta.get("price"),
                import_hash=_make_hash(tx_date, description, amount, statement_label),
                account_statement=statement_label,
            )
            results.append(tx)

    return results, iban
