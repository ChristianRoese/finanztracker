# Finanztracker

Persönliches Finanz-Tracking für DKB-Kontoauszüge mit ETF-Portfolio-Tracking und KI-Kategorisierung.

## Stack
- **Backend**: FastAPI + SQLModel (SQLite)
- **PDF-Parsing**: pdfplumber
- **Kategorisierung**: Claude Haiku API (regelbasiert + KI-Fallback)
- **ETF-Preise**: Yahoo Finance (ISIN-basiert via ISIN → Ticker → `.DE` Börse, immer EUR)
- **Frontend**: Vanilla HTML/CSS/JS (kein Build-Step)
- **Deployment**: Docker + docker-compose

---

## Setup

### 1. Repository klonen & Konfiguration

```bash
git clone <repo> finanztracker
cd finanztracker
cp .env.example .env
```

`.env` anpassen:
```env
ANTHROPIC_API_KEY=sk-ant-...
DB_PATH=/data/finanztracker.db
CORS_ORIGINS=http://localhost:8080,http://192.168.1.100:8080
```

### 2. Docker starten

```bash
docker compose up -d --build
```

Dashboard erreichbar unter: **http://localhost:8080**

### 3. Ersten Kontoauszug importieren

1. Browser → **PDF Import** Tab
2. DKB-Kontoauszug PDF reinziehen
3. Transaktionen werden automatisch geparst und kategorisiert

---

## Proxmox LXC Deployment

```bash
# Im LXC (Debian/Ubuntu):
apt-get install -y docker.io docker-compose-plugin
git clone <repo> /opt/finanztracker
cd /opt/finanztracker
cp .env.example .env && nano .env
docker compose up -d

# Autostart via systemd
cat > /etc/systemd/system/finanztracker.service << EOF
[Unit]
Description=Finanztracker
After=docker.service
Requires=docker.service

[Service]
WorkingDirectory=/opt/finanztracker
ExecStart=/usr/bin/docker compose up
ExecStop=/usr/bin/docker compose down
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl enable --now finanztracker
```

---

## Entwicklung (lokal ohne Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export ANTHROPIC_API_KEY=sk-ant-...
export DB_PATH=./data/finanztracker.db
mkdir -p data

uvicorn backend.main:app --reload --port 8080
```

---

## Kategorien

| Kategorie | Beispiele |
|---|---|
| Lebensmittel | Globus, ALDI, Rewe, Biomarkt, Bäckereien, Rossmann |
| Lieferando | Lieferando, Domino's, Call a Pizza |
| Restaurant/Café | Coffee Fellows, Döner, McDonald's, Starbucks, Al Porto |
| Amazon | Amazon, AMZN |
| Streaming | Netflix, Spotify, Disney+, Audible, Kindle, Apple.com.de |
| Gaming | Blizzard, Steam, G2A, CCP Games, Warhammer |
| Versicherung | Signal Iduna, HUK-Coburg, Cosmos |
| Kredit & Schulden | Kreditabzahlung, Santander, Consors Finanz |
| Investments | ETF-Sparpläne, Wertpapierabrechnungen, Trade Republic |
| Transport & Auto | Tankstelle, KFZ-Steuer, Agip, Warnowtunnel, Flughafen |
| Gesundheit | Apotheke, Klinik-Service, Fielmann, Reha |
| Sonstiges | Alles andere |
| Einnahmen | Gehalt, Rückerstattungen |

---

## ETF-Positionen

Aktive Positionen (Stand März 2026):

| ISIN | Name | Ticker |
|---|---|---|
| IE00BK1PV551 | Xtrackers MSCI World 1D | XDWD.DE (via XDWL.L, USD→EUR) |
| IE00B3YLTY66 | SPDR MSCI ACWI IMI | SPYI.DE |

**Hinweis SPYI Split**: 25:1 Split am 23.02.2026 – alle Käufe vor diesem Datum wurden angepasst.

Neue ISINs eintragen in `backend/services/etf_service.py`:
- `ISIN_TO_TICKER` – Ticker für Preisabfrage
- `ISIN_TO_NAME` – Anzeigename
- `ISIN_ALIAS` – falls alte ISIN auf neue umgeleitet werden soll (z.B. Fondsfusion)

ETFs mit `fully_sold=True` werden aus dem Portfolio ausgeblendet. Wird nach jedem Import automatisch gesetzt wenn Net-Shares ≤ 0.

---

## Preisabfrage (ETF)

Ablauf:
1. `ISIN_TO_TICKER` Mapping → Ticker (z.B. `XDWL.L`)
2. Yahoo Finance Chart-API → Preis + Währung
3. Wenn Währung ≠ EUR: automatische Umrechnung via `USDEUR=X` (live)

---

## API Dokumentation

Swagger UI: **http://localhost:8080/docs**

### Wichtigste Endpoints

```
POST /api/import/pdf              – PDF hochladen & importieren
GET  /api/transactions            – Transaktionsliste (filter: month, category, account_id)
PUT  /api/transactions/{id}/category – Kategorie manuell setzen
GET  /api/transactions/summary    – Monatliche Zusammenfassung
GET  /api/transactions/categories – Kategorie-Breakdown
GET  /api/etf/positions           – Portfolio mit aktuellem Wert
POST /api/etf/refresh-prices      – Preise via Yahoo Finance (ISIN-basiert) aktualisieren
GET  /api/etf/forecast            – 5-Jahres-Prognose (Best/Casual/Worst)
GET  /api/reports/monthly/{year}/{month} – Monatsbericht
GET  /api/reports/trends          – Kategorien-Trends (12 Monate)
```

---

## Projektstruktur

```
finanztracker/
├── backend/
│   ├── main.py              # FastAPI App + Static Files
│   ├── database.py          # SQLite Engine
│   ├── models/
│   │   ├── transaction.py   # Transaction SQLModel
│   │   ├── etf.py           # ETFPosition, ETFPurchase, ETFPrice
│   │   └── account.py       # BankAccount SQLModel
│   ├── routers/
│   │   ├── import_.py       # PDF Upload & Parse + fully_sold Auto-Update
│   │   ├── transactions.py  # CRUD + Filter + Summary
│   │   ├── reports.py       # Monatsberichte + Trends
│   │   └── etf.py           # Portfolio & Preise
│   └── services/
│       ├── pdf_parser.py    # DKB PDF → ParsedTransaction
│       ├── categorizer.py   # Regelbasiert + Claude Haiku
│       └── etf_service.py   # Yahoo Finance + Portfolio-Berechnung
├── frontend/
│   ├── index.html           # SPA
│   └── static/
│       ├── css/style.css
│       └── js/
│           ├── app.js       # Navigation + Dashboard + Tx (sortierbare Spalten)
│           ├── charts.js    # Chart.js Wrappers (filterabhängiger Monatsvergleich)
│           ├── import.js    # Drag & Drop Upload
│           └── etf.js       # ETF Portfolio View
├── data/                    # SQLite DB (gitignored)
├── tasks/
│   ├── todo.md              # Sprint Board
│   └── lessons.md           # Lessons Learned
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## Lizenz

Privates Tool – kein öffentliches Release geplant.
