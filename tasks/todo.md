# Finanztracker – Task Board

_Stand: März 2026_

---

## ✅ Erledigt

### Foundation
- [x] FastAPI + SQLModel + Docker Setup
- [x] DKB PDF-Parser (text-basiert, mehrzeilig, Seitenumbrüche)
- [x] Import-Router: PDF → Parse → Kategorisieren → Speichern
- [x] Duplikat-Erkennung via import_hash (SHA256)
- [x] Transaktionen CRUD + Filter (Monat, Kategorie, Konto)
- [x] Monatsbericht + Kategorien-Trends Endpoints
- [x] Multi-Account Support (IBAN-Erkennung aus PDF)

### ETF Portfolio
- [x] ETFPosition + ETFPurchase + ETFPrice Modelle
- [x] Wertpapierabrechnungen aus PDF automatisch als ETF-Käufe erkennen
- [x] ETF-Namen aus `ISIN_TO_NAME` Mapping (nicht aus PDF-Rohtext)
- [x] `ISIN_ALIAS` für Fonds-Umbenennungen (alte ISIN → neue ISIN)
- [x] `fully_sold` Flag: automatisch nach Import setzen wenn Net-Shares ≤ 0
- [x] Preisabfrage via Yahoo Finance (ISIN-basiert, immer EUR, USD→EUR live-Umrechnung)
- [x] SPYI Split 25:1 vom 23.02.2026 angewendet
- [x] Portfolio-Summary, CAGR, 5-Jahres-Prognose (Best/Casual/Worst)

### Frontend
- [x] Dashboard: KPIs, Kategorie-Balken, Donut, Monatsvergleich, Trend
- [x] Jahr/Monat-Filter: Monat nur aktiv wenn Jahr gewählt
- [x] Monatsvergleich zentriert auf gewählten Monat (nicht immer letzte 6)
- [x] ETF-Portfolio Tab
- [x] Import Tab mit Drag & Drop
- [x] Transaktionen: sortierbare Spalten (Datum, Händler, Kategorie, Betrag)
- [x] Transaktionsliste: Pagination, Suche, manuelle Kategorie-Änderung

### Kategorisierung
- [x] Regelbasierte Regex-Patterns (Vorfilter vor API-Call)
- [x] Erweiterung der Regex-Patterns (März 2026): Bäckereien, Audible, Kindle, Apple.com.de, Agip, Warnowtunnel, Al Porto, Asian Ways, Starbucks, Klinik-Service, Fielmann, Trade Republic, SumUp-Cafés, Warhammer u.v.m.
- [x] Claude Haiku Batch-Kategorisierung (Fallback für unbekannte Merchants)

---

## 📋 Offen / Nächste Schritte

### Dringend
- [ ] **Haiku Re-Kategorisierung**: Nach Aufladen des API-Guthabens alle 560 "Sonstiges"-Transaktionen nochmal durch Haiku laufen lassen
- [ ] **ETF-Daten**: Verkäufe aus Q4 2025 nachtragen (IE00BK1PV551 – genaue Daten aus Broker-App holen)
- [ ] **ETF-Daten**: Fehlende März-Sparpläne prüfen (250€ XDWD + 50€ SPYI)

### Features
- [ ] Manuelle Transaktionen hinzufügen (Formular)
- [ ] Kategorie-Regeln persistent speichern (DB statt nur Code)
- [ ] CSV-Export
- [ ] Spar-Tipps: Anomalie-Erkennung (Monat X deutlich höher als Ø)

### Backlog
- [ ] Weitere Banken (Sparkasse, ING) via konfigurierbarem Parser
- [ ] Budget-Ziele pro Kategorie mit Ampel
- [ ] Telegram-Bot: monatliche Push-Zusammenfassung
- [ ] Obsidian-Integration: Monatsbericht als Markdown exportieren

---

## 🐛 Bekannte Eigenheiten

- DKB schreibt Merchant-Namen mit Punkten statt Leerzeichen (`Coffee.Fellows`) – Regex-Patterns müssen `[\s.]` nutzen
- SumUp-Transaktionen: eigentlicher Merchant steht nach `SUMUP...`
- finanzen.net blockiert Scraping (403) – nicht nutzbar als Preisquelle
- Yahoo Finance Search gibt für IE00BK1PV551 nur `XDWL.L` (USD) zurück, kein `.DE` Ticker → Umrechnung nötig
