# Finanztracker

Persönliches Finanz-Tracking für DKB-Kontoauszüge mit ETF-Portfolio-Tracking und KI-Kategorisierung.

## Stack
- **Backend**: FastAPI + SQLModel (SQLite)
- **PDF-Parsing**: pdfplumber
- **Kategorisierung**: Claude Haiku API (regelbasiert + KI-Fallback)
- **ETF-Preise**: yfinance
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
docker-compose up -d
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
| Lebensmittel | Globus, ALDI, Rewe, Biomarkt |
| Lieferando | Lieferando, Domino's, Call a Pizza |
| Restaurant/Café | Coffee Fellows, Döner, McDonald's |
| Amazon | Amazon, AMZN |
| Streaming | Netflix, Spotify, Disney+, Crunchyroll |
| Gaming | Blizzard, Steam, G2A, CCP Games |
| Versicherung | Signal Iduna, HUK-Coburg, Cosmos |
| Kredit & Schulden | Kreditabzahlung, Santander KFZ |
| Investments | ETF-Sparpläne, Wertpapierabrechnungen |
| Transport & Auto | Tankstelle, KFZ-Steuer, Autohaus |
| Gesundheit | Apotheke, Shop Apotheke, Petfood |
| Sonstiges | Alles andere |
| Einnahmen | Gehalt, Rückerstattungen |

---

## ETF ISIN → Ticker Mapping

Bekannte ETFs sind in `backend/services/etf_service.py` vorkonfiguriert:

```python
ISIN_TO_TICKER = {
    "IE00BK1PV551": "XDWD.DE",   # Xtrackers MSCI World 1D
    "IE00B3YLTY66": "SPYW.DE",   # SPDR MSCI ACWI IMI
}
```

Neue ETFs einfach ergänzen. Ticker findest du auf justetf.com oder Yahoo Finance.

---

## API Dokumentation

Swagger UI: **http://localhost:8080/docs**

### Wichtigste Endpoints

```
POST /api/import/pdf              – PDF hochladen & importieren
GET  /api/transactions            – Transaktionsliste (filter: month, category)
PUT  /api/transactions/{id}/category – Kategorie manuell setzen
GET  /api/transactions/summary    – Monatliche Zusammenfassung
GET  /api/transactions/categories – Kategorie-Breakdown
GET  /api/etf/positions           – Portfolio mit aktuellem Wert
POST /api/etf/refresh-prices      – Preise via yfinance aktualisieren
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
│   │   └── etf.py           # ETFPosition, ETFPurchase, ETFPrice
│   ├── routers/
│   │   ├── import_.py       # PDF Upload & Parse
│   │   ├── transactions.py  # CRUD + Filter + Summary
│   │   └── etf.py           # Portfolio & Preise
│   └── services/
│       ├── pdf_parser.py    # DKB PDF → ParsedTransaction
│       ├── categorizer.py   # Regelbasiert + Claude Haiku
│       └── etf_service.py   # yfinance + Portfolio-Berechnung
├── frontend/
│   ├── index.html           # SPA
│   └── static/
│       ├── css/style.css
│       └── js/
│           ├── app.js       # Navigation + Dashboard + Tx
│           ├── charts.js    # Chart.js Wrappers
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
