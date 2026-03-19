# Finanztracker – Task Board

## Status: Sprint 2 aktiv

---

## ✅ Erledigt

### Sprint 1 – Foundation
- [x] **S1-01** `requirements.txt` + `Dockerfile` + `docker-compose.yml` erstellen
- [x] **S1-02** FastAPI app skeleton (`main.py`) mit Health-Endpoint
- [x] **S1-03** SQLite DB-Setup via SQLModel (`database.py`)
- [x] **S1-04** Transaction-Modell + Migration (`models/transaction.py`)
- [x] **S1-05** DKB PDF-Parser implementieren (`services/pdf_parser.py`)
- [x] **S1-06** Import-Router (`routers/import_.py`) – POST /api/import/pdf
- [x] **S1-07** Kategorisierungs-Service (`services/categorizer.py`)
- [x] **S1-08** Transactions-Router – GET /api/transactions + /api/transactions/summary
- [x] **S1-09** Frontend Grundgerüst (index.html + style.css)
- [x] **S1-10** Frontend: PDF-Upload UI mit Drag & Drop
- [x] **S1-11** Frontend: Dashboard-Charts (Monatsvergleich, Donut)
- [x] **S1-12** Frontend: Transaktionsliste mit Filter + manuelle Kategorie-Änderung
- [x] **S1-13** Docker-Build testen + README mit Setup-Anleitung

### Sprint 2 – ETF Portfolio Tracking (teilweise)
- [x] **S2-01** ETFPosition + ETFPurchase + ETFPrice Modelle
- [x] **S2-02** ETF-Service: yfinance Preis-Fetching (ISIN → Ticker-Mapping)
- [x] **S2-03** Wertpapierabrechnungen aus PDF-Import automatisch als ETF-Käufe erkennen
- [x] **S2-04** ETF-Router: Positionen, Performance, Preise refreshen
- [x] **S2-06** Hintergrund-Job: täglicher Preis-Refresh (APScheduler)

### Sprint 3 – Reports (teilweise)
- [x] **S3-01** Monatsbericht-Endpoint (`GET /api/reports/monthly/{year}/{month}`)
- [x] **S3-02** Kategorien-Trends (`GET /api/reports/trends`)

---

## 🔄 Sprint 2 – ETF Portfolio Tracking (offen)

- [ ] **S2-05** Frontend: ETF-Portfolio Tab
  - Gesamtwert, invested vs. aktuell
  - Performance pro Position
  - Sparplan-Verlauf (Kaufhistorie)

---

## 📋 Sprint 3 – Reports & Komfort (offen)

- [ ] **S3-03** Duplikat-Erkennung beim PDF-Import (gleiche Buchung doppelt importieren verhindern)
- [ ] **S3-04** Manuelle Transaktionen hinzufügen (Formular)
- [ ] **S3-05** Kategorie-Regeln (z.B. "Globus" → immer "Lebensmittel") persistent speichern
- [ ] **S3-06** CSV-Export
- [ ] **S3-07** Spar-Tipps: automatische Anomalie-Erkennung (Monat X deutlich höher als Ø)

---

## 💡 Backlog / Ideen

- Unterstützung weiterer Banken (Sparkasse, ING) via konfigurierbarem Parser
- Budget-Ziele pro Kategorie mit Ampel-Anzeige
- Obsidian-Integration: Monatsbericht als Markdown-Note exportieren
- Telegram-Bot: monatliche Push-Zusammenfassung
- Mehrere Konten / Depots verwalten

---

## 🐛 Bugs
_(noch keine)_
