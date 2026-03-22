# Lessons Learned – Finanztracker

_Wird nach jedem Fix / jeder Korrektur ergänzt._

---

## DKB PDF-Parsing

### 2026-03 – Projektstart
- DKB-PDFs haben keine echte Tabellenstruktur; text-basiertes Parsing mit `extract_text()` ist robuster als `extract_table()`
- Kontostand-Zeilen erkennen: kein Datum in Spalte 0, Text enthält "Kontostand am"
- Beträge: deutsches Format `1.234,56` → `replace('.', '').replace(',', '.')` → float
- Wertpapierabrechnungen: Text enthält "Wertpapierabrechnung" – separat als ETF-Kauf extrahieren
- Mehrzeilige Beschreibungen: Heuristik über Datum-Regex als Zeilentrennzeichen
- ETF-Position Name: **niemals** aus der PDF-Rohbeschreibung nehmen – immer aus `ISIN_TO_NAME` Mapping (sonst landet "Wertpapierabrechnung / Wert: 07.02.2024 Depot..." als Name)

## ETF-Daten & Preise

### 2026-03 – Korrekturen
- ISIN ≠ Ticker: IE00BJ0KDQ92 und IE00BK1PV551 sind **verschiedene ETFs** (1C vs. 1D), auch wenn sie denselben Ticker teilen können. Nie Käufe zwischen Positionen migrieren ohne explizite Nutzerbestätigung.
- Yahoo Finance Search-API liefert für manche ISINs keinen `.DE` Ticker (z.B. IE00BK1PV551 → nur XDWL.L in USD). Lösung: Ticker aus `ISIN_TO_TICKER` Mapping, Preis in USD holen, live mit `USDEUR=X` umrechnen.
- finanzen.net blockiert alle Requests mit HTTP 403 (Cloudflare/Bot-Schutz) – **nicht als Datenquelle nutzbar**.
- **SPYI Split**: IE00B3YLTY66 hatte 25:1 Split am 23.02.2026. Alle Käufe VOR diesem Datum: `shares × 25`, `price_eur ÷ 25`.
- `fully_sold` Feld: wird nach jedem Import automatisch gesetzt wenn Net-Shares ≤ 0.001. Verhindert dass abgeschlossene Positionen im Portfolio auftauchen.
- `ISIN_ALIAS` Mapping für umbenannte/fusionierte Fonds: alte ISIN → neue ISIN, damit PDFs mit alter ISIN trotzdem zur richtigen Position gehen.

### DB-Bereinigung
- Nach einem vollständigen DB-Purge und Reimport: die lokale `data/finanztracker.db` ist dasselbe Volume wie im Container. Ein `docker compose up -d --build` stellt die Daten **nicht** wieder her wenn die Datei leer ist – die DB liegt auf dem Host, nicht im Image.
- `transaction` ist ein reserviertes SQL-Keyword → immer mit Anführungszeichen: `DELETE FROM "transaction"`

## Claude API

### Kategorisierung
- Haiku ist für einfache Klassifikation völlig ausreichend und ~10× günstiger als Sonnet
- Bei leerem API-Guthaben (`credit balance too low`) schlägt jeder Call sofort mit 400 fehl – Guthaben unter console.anthropic.com aufladen
- Regelbasierte Vor-Filterung vor dem API-Call spart signifikant Tokens: ~60% der Transaktionen werden per Regex korrekt kategorisiert
- Regex-Patterns müssen **Punkte als Trennzeichen** berücksichtigen: DKB schreibt `Coffee.Fellows`, `Hai.Asia` etc. → `[\s.]` statt nur `\s`
- SumUp-Transaktionen: Merchant-Name steht nach `SUMUP...` → `sumup.*kaf|sumup.*asia` Pattern nötig

## SQLite / SQLModel

- `col()` aus sqlmodel zwingend für `.desc()` / `.asc()` — ohne `col()` AttributeError zur Laufzeit
- SQL-Aggregation via `func.sum()` + `.group_by()` bevorzugen
- `transaction` ist ein reserviertes SQL-Keyword → immer mit Anführungszeichen
- APScheduler: eigene `Session(engine)` im Job, nie Request-Session weitergeben

## Docker / Deployment

- `docker compose up -d --build` baut neu und startet – Volume-Daten bleiben erhalten
- DB liegt unter `./data/finanztracker.db` (Host) = `/data/finanztracker.db` (Container)
- Nach DB-Purge: Container-Neustart stellt keine Daten wieder her (korrekt so)

## Frontend (Vanilla JS ES Modules)

- `escHtml()` auf alle user-originären Daten, auch in `onclick`-Attributen
- Chart.js: vor Neuerstellen `chartInstance.destroy()` aufrufen
- Sortierbare Tabellen: Sort-State als Modul-Variable (`txSort = { col, dir }`), Click-Handler nach DOM-Aufbau registrieren
- Monatsvergleich-Chart: immer alle Summary-Daten übergeben (`summaryRaw`), Filterlogik im Chart selbst (zentriert auf gewählten Monat, Jahr = alle Monate, kein Filter = letzte 6)
- Jahr-/Monats-Filter: Monat nur aktivierbar wenn Jahr gewählt
- Trend-Chart: trailing empty months abschneiden, 12 Monate, Jahreslabels bei Jahreswechsel
