# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projektübersicht
Persönliches Finanz-Tracking-Tool für DKB-Kontoauszüge (PDF) mit ETF-Portfolio-Tracking und KI-gestützter Kategorisierung via Claude API. Self-hosted via Docker auf Proxmox.

## Lokale Entwicklung

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-... DB_PATH=./data/finanztracker.db
mkdir -p data
uvicorn backend.main:app --reload --port 8080
```

Swagger UI: http://localhost:8080/docs

## Stack
- **Backend**: FastAPI (Python 3.12) + SQLModel (SQLite ORM)
- **PDF-Parsing**: pdfplumber
- **KI**: Anthropic Claude API (claude-haiku-4-5 für Kategorisierung – günstig + schnell)
- **Frontend**: Vanilla HTML/CSS/JS (kein Build-Step, kein Node)
- **DB**: SQLite via `/data/finanztracker.db` (Volume-mounted)
- **Deployment**: Docker + docker-compose (Proxmox LXC)
- **ETF-Preise**: yfinance (polling, kein Webhook)

## Architektur

```
finanztracker/
├── backend/
│   ├── main.py              # FastAPI app, CORS, lifespan
│   ├── database.py          # SQLite engine, session factory
│   ├── models/
│   │   ├── transaction.py   # Transaction, Category SQLModel
│   │   └── etf.py           # ETFPosition, ETFPrice SQLModel
│   ├── routers/
│   │   ├── transactions.py  # CRUD + filter endpoints
│   │   ├── import_.py       # PDF upload + parse endpoint
│   │   ├── etf.py           # ETF positions + price fetch
│   │   └── reports.py       # Monthly summary, category breakdown
│   └── services/
│       ├── pdf_parser.py    # pdfplumber → raw transactions
│       ├── categorizer.py   # Claude API auto-categorization
│       └── etf_service.py   # yfinance price fetching
├── frontend/
│   ├── index.html           # Dashboard (SPA)
│   └── static/
│       ├── css/style.css
│       └── js/
│           ├── app.js       # Main controller
│           ├── charts.js    # Chart.js wrappers
│           ├── import.js    # PDF upload UI
│           └── etf.js       # ETF portfolio UI
├── data/                    # SQLite DB (gitignored)
├── tasks/
│   ├── todo.md
│   └── lessons.md
├── scripts/
│   └── seed.py              # Optional: seed historische Daten
├── .env.example
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Kernprinzipien
- **Simplicity First**: Kein unnötiger Overhead. Vanilla JS statt Framework. SQLite statt Postgres.
- **No Laziness**: Vollständige Implementierung, keine TODOs im Code hinterlassen.
- **Minimal Impact**: Änderungen immer mit minimalem Footprint. Keine Breaking Changes ohne Migration.
- **Root Cause Only**: Bugs an der Wurzel fixen, nicht mit Workarounds pflastern.

## Coding-Standards
- Python: type hints überall, Pydantic-Schemas für alle API-Requests/Responses
- Keine globalen Variablen; Dependencies via FastAPI `Depends()`
- Alle DB-Operationen in Services, nicht in Routers
- Frontend: ES modules, kein jQuery, kein Webpack
- Fehlerbehandlung: immer explizit, nie `except: pass`

## Datenmodell (Kernentitäten)

### Transaction
```python
id: int (PK)
date: date
description: str          # Rohtext aus PDF
merchant: str             # bereinigt (z.B. "Globus Markthalle")
amount: float             # negativ = Ausgabe, positiv = Einnahme
category: str             # auto oder manuell
category_source: str      # "ai" | "manual" | "rule"
account_statement: str    # z.B. "2/2026"
month: str                # "2026-01" (für Grouping)
created_at: datetime
```

### ETFPosition
```python
id: int (PK)
isin: str
wkn: str
name: str
monthly_amount: float     # Sparplan-Betrag
```

### ETFPurchase
```python
id: int (PK)
position_id: int (FK)
date: date
price_eur: float
shares: float
total_eur: float
source: str               # "import" | "manual"
```

### ETFPrice
```python
id: int (PK)
position_id: int (FK)
date: date
price_eur: float
```

## API-Endpunkte

### Import
- `POST /api/import/pdf` – PDF hochladen, parsen, kategorisieren, speichern
- `GET  /api/import/status/{job_id}` – Import-Status (async)

### Transactions
- `GET  /api/transactions` – Liste mit Filter (month, category, limit)
- `PUT  /api/transactions/{id}/category` – Manuelle Kategorie setzen
- `GET  /api/transactions/summary` – Monatliche Zusammenfassung
- `GET  /api/transactions/categories` – Kategorie-Breakdown

### ETF
- `GET  /api/etf/positions` – Alle Positionen + aktueller Wert
- `POST /api/etf/positions` – Neue Position anlegen
- `POST /api/etf/refresh-prices` – yfinance polling
- `GET  /api/etf/performance` – Performance-Übersicht

### Reports
- `GET  /api/reports/monthly/{year}/{month}` – Monatsbericht
- `GET  /api/reports/trends` – Kategorien-Trends über Zeit

## Kategorien (fest definiert)
```python
CATEGORIES = [
    "Lebensmittel", "Lieferando", "Restaurant/Café", "Amazon",
    "Streaming", "Gaming", "Versicherung", "Kredit & Schulden",
    "Investments", "Transport & Auto", "Gesundheit", "Sonstiges",
    "Einnahmen"
]
```

## DKB PDF-Parser-Logik
DKB-Kontoauszüge haben ein konsistentes Format:
- Tabelle mit Spalten: Datum | Erläuterung | Betrag Soll EUR | Betrag Haben EUR
- Kontostand-Zeilen überspringen
- Betrag: deutsches Format → `1.234,56` → float
- Datum: `DD.MM.YYYY`
- Mehrzeilige Erläuterungen zusammenführen (pdfplumber gibt Zeilen zurück)

## Claude API Kategorisierung
- Modell: `claude-haiku-4-5-20251001` (günstigste Option, für einfache Klassifikation ausreichend)
- Batch-Calls: max 20 Transaktionen pro Request
- System-Prompt gibt Kategorien + Beispiele vor
- Response: JSON Array `[{"id": 0, "category": "Lebensmittel"}, ...]`
- Fallback: "Sonstiges" bei API-Fehler

## Environment Variables
```env
ANTHROPIC_API_KEY=sk-ant-...
DB_PATH=/data/finanztracker.db
CORS_ORIGINS=http://localhost:3000,http://192.168.x.x:8080
```

## Docker
- Single container: FastAPI served via uvicorn, Frontend als static files
- Port: 8080
- Volume: `./data:/data` (SQLite DB persistent)
- Restart: `unless-stopped`

## ETF-Erweiterung
Neue ISINs in `backend/services/etf_service.py` → `ISIN_TO_TICKER` dict eintragen. Ticker auf justetf.com oder Yahoo Finance finden.

## Bekannte DKB-Eigenheiten
- Wertpapierabrechnungen tauchen als reguläre Buchungen auf → via "Wertpapierabrechnung" im Text erkennen und als ETF-Kauf importieren
- Kontostand-Zeilen haben kein Datum in der ersten Spalte → überspringen
- Mehrzeilige Beschreibungen: pdfplumber gibt manchmal Zeilen-Splits → per Heuristik zusammenführen (Datum-Regex als Zeilentrenner)
- Beträge können fehlen wenn Spalte leer (z.B. Haben-Spalte bei Ausgaben)
