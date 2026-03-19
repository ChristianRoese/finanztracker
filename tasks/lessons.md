# Lessons Learned – Finanztracker

_Wird nach jedem Fix / jeder Korrektur ergänzt._

---

## DKB PDF-Parsing

### 2026-03 – Projektstart
- DKB-PDFs haben keine echte Tabellenstruktur im PDF-Sinne; pdfplumber's `extract_table()` funktioniert besser als `extract_text()` mit manuellen Splits
- Kontostand-Zeilen erkennen: kein Datum in Spalte 0, Text enthält "Kontostand am"
- Beträge: deutsches Format `1.234,56` → `replace('.', '').replace(',', '.')` → float
- Wertpapierabrechnungen: Text enthält "Wertpapierabrechnung" oder "Wertp.Abrechn." – nicht als normale Transaktion behandeln, separat als ETF-Kauf extrahieren
- Mehrzeilige Beschreibungen entstehen wenn pdfplumber eine Zeile bricht – Heuristik: Zeile ohne Datum-Pattern und ohne Betrag → an vorherige Zeile anhängen

## Claude API

### Kategorisierung
- Haiku ist für einfache Klassifikation (Text → eine von N Kategorien) völlig ausreichend und ~10x günstiger als Sonnet
- Batch-Größe 20 ist guter Kompromiss; größere Batches → gelegentliche Timeout-Fehler
- System-Prompt muss Kategorien explizit auflisten + 2-3 Beispiele pro Kategorie geben, sonst halluziniert das Modell eigene Kategorien
- Response immer als JSON anfordern, nie als Freitext

## SQLite / SQLModel

### 2026-03 – Code Review
- `col()` aus sqlmodel ist zwingend nötig für `.desc()` / `.asc()` auf Modell-Attributen — ohne `col()` gibt es einen `AttributeError` zur Laufzeit (`col(ETFPrice.date).desc()` ✓)
- SQL-Aggregation via `func.sum()`, `func.count()`, `.group_by()` immer bevorzugen gegenüber Python-side Aggregation (alle Rows laden + defaultdict)
- `order_by(text("label_name"))` für Sortierung nach benanntem Aggregat
- APScheduler BackgroundScheduler braucht eigene `Session(engine)` im Job — nie die Request-Session weitergeben
- `get_session()` ist ein Generator → Return Type: `Generator[Session, None, None]`

## Docker / Deployment

_(noch nichts)_

## Frontend (Vanilla JS ES Modules)

### 2026-03 – Code Review
- `escHtml()` auf ALLE user-originären Daten — auch in `onclick`-Attributen. Inline-Event-Handler sind ein XSS-Vektor
- Raw `fetch()` und zentrale `apiFetch()` nicht mischen — immer über eine Funktion routen
- Event-Listener-Guard in wiederholten Render-Funktionen: `if (el._bound) return; el._bound = true;` oder `.onclick = fn` (überschreibt automatisch)
- Chart.js: vor jedem Neuerstellen `chartInstance.destroy()` aufrufen
- Empty States mit `createElement`/`textContent` statt `innerHTML` — kein XSS
- `Promise.all` mit identischen API-Calls ist ein häufiger Copy-Paste-Bug
- Liniendiagramme: `pointRadius: 0` + `pointHoverRadius: 4` für cleanen Look mit Hover-Feedback
