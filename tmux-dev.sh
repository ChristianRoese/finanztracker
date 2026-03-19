#!/usr/bin/env bash
# Finanztracker – Parallele Agent-Session
# Startet 3 Claude-Agenten in separaten tmux-Panes.
# Verwendung: ./tmux-dev.sh

set -euo pipefail

SESSION="finanztracker-dev"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Bestehende Session killen
tmux kill-session -t "$SESSION" 2>/dev/null || true

# Neue Session anlegen (detached)
tmux new-session -d -s "$SESSION" -c "$DIR" -x 240 -y 60

# Pane 1 rechts neben Pane 0
tmux split-window -h -t "$SESSION:0" -c "$DIR"

# Pane 2 unter Pane 0 (volle Breite unten via main-vertical)
tmux split-window -v -t "$SESSION:0.0" -c "$DIR"
tmux select-layout -t "$SESSION:0" main-vertical

# Pane-Titel
tmux set-option -t "$SESSION" pane-border-status top
tmux set-option -t "$SESSION" pane-border-format "#{pane_title}"
tmux select-pane -t "$SESSION:0.0" -T "backend-quality"
tmux select-pane -t "$SESSION:0.1" -T "backend-features"
tmux select-pane -t "$SESSION:0.2" -T "frontend"

# ── AGENT 1: backend-quality ────────────────────────────────────────────────
read -r -d '' PROMPT_Q << 'EOF' || true
Du bist ein Senior Python-Entwickler und reviewst den Backend-Code eines FastAPI Finanztracker-Projekts.
Behebe alle Bugs, Inkonsistenzen und Qualitätsprobleme eigenständig bis zur Fertigstellung.

SCOPE (nur diese Dateien anfassen):
- backend/services/pdf_parser.py
- backend/services/categorizer.py
- backend/services/etf_service.py
- backend/routers/transactions.py
- backend/routers/etf.py
- backend/routers/import_.py
- backend/models/transaction.py
- backend/models/etf.py
- backend/database.py

VERBOTEN: backend/main.py NICHT anfassen.

AUFGABEN:

1. pdf_parser.py — statement_label nutzen:
   parse_pdf() bekommt statement_label aber nutzt es nie intern.
   Fix: ParsedTransaction um Feld account_statement: str = "" erweitern,
   in parse_pdf() befüllen. _make_hash() soll statement_label einbeziehen.

2. pdf_parser.py — Type Hint korrigieren:
   parse_pdf() hat `file_bytes: bytes` aber bekommt io.BytesIO.
   Fix: from typing import BinaryIO; Parameter-Typ auf BinaryIO setzen.

3. routers/transactions.py — HTTPException Top-Level:
   HTTPException wird innerhalb von Funktionen importiert (lazy import).
   Fix: an den Dateianfang verschieben.

4. routers/etf.py — Annotated Depends:
   create_position() nutzt `session: Session = Depends(get_session)` ohne Annotated.
   Fix: auf Annotated[Session, Depends(get_session)] umstellen.
   HTTPException importieren, doppelte ISIN mit 409 abfangen.

5. routers/transactions.py — SQL Aggregation:
   monthly_summary() laedt alle Transaktionen in Memory.
   Fix: SQL Aggregation mit sqlalchemy func.sum, func.count, group_by.
   Ausgabe-Format bleibt: [{month, income, expenses, net, tx_count}]

6. Weitere Qualitaetsprobleme die du findest: eigenstaendig beheben.

Schreibe am Ende eine Zusammenfassung aller Aenderungen.
EOF

tmux send-keys -t "$SESSION:0.0" "claude --dangerously-skip-permissions -p \"$PROMPT_Q\"" Enter

# ── AGENT 2: backend-features ───────────────────────────────────────────────
read -r -d '' PROMPT_F << 'EOF' || true
Du bist ein Senior Python-Entwickler und implementierst fehlende Features in einem FastAPI Finanztracker.
Arbeite eigenstaendig bis zur Fertigstellung.

SCOPE (nur diese Dateien):
- backend/routers/reports.py (NEU)
- backend/services/scheduler.py (NEU)
- backend/main.py (NUR Router-Registration + Scheduler im lifespan)
- tasks/todo.md (Checkboxen aktualisieren)

VERBOTEN: Keine anderen Dateien aendern.

CODEBASE-PATTERNS:
- Router: APIRouter(prefix="/api/...", tags=[...])
- Session: Annotated[Session, Depends(get_session)] aus backend.database
- Transaction Modell: backend.models.transaction; CATEGORIES Liste dort
- ETF Service: refresh_all_prices(session) in backend.services.etf_service
- APScheduler bereits in requirements.txt: apscheduler==3.10.4

AUFGABEN:

1. backend/routers/reports.py erstellen:

   GET /api/reports/monthly/{year}/{month}
   Response: {month, income, expenses, net, savings_rate, categories: [{category, total}]}
   SQL: WHERE month == f"{year}-{month:02d}"

   GET /api/reports/trends?months=6
   Response: {months: ["2025-10",...], series: [{category, values: [312.0,...]}]}
   Nur Kategorien die in mindestens einem Monat > 0 hatten.

2. backend/services/scheduler.py erstellen:
   APScheduler BackgroundScheduler, Job taeglich 18:00 Uhr.
   Job oeffnet eigene DB-Session und ruft refresh_all_prices() auf.
   Funktion: start_scheduler() -> BackgroundScheduler
   Job-Fehler loggen, Scheduler laeuft weiter.

3. backend/main.py anpassen:
   - reports Router importieren + registrieren
   - Scheduler in lifespan starten/stoppen
   NUR diese zwei Aenderungen.

4. tasks/todo.md: abgeschlossene Tasks abhaken (Sprint 1 komplett, Sprint 2 soweit implementiert).

Schreibe am Ende eine Zusammenfassung aller Aenderungen.
EOF

tmux send-keys -t "$SESSION:0.1" "claude --dangerously-skip-permissions -p \"$PROMPT_F\"" Enter

# ── AGENT 3: frontend ────────────────────────────────────────────────────────
read -r -d '' PROMPT_UI << 'EOF' || true
Du bist ein Senior Frontend-Entwickler und modernisierst ein Finanztracker-Frontend.
Vanilla JS ES Modules, kein Framework, kein Build-Step. Arbeite eigenstaendig bis zur Fertigstellung.

SCOPE: Nur frontend/ Verzeichnis. Keine Backend-Aenderungen.

STRUKTUR:
- index.html: SPA mit 4 Views (dashboard, transactions, etf, import)
- static/js/app.js: Main Controller
- static/js/charts.js: Chart.js Wrappers
- static/js/etf.js: ETF Portfolio View
- static/js/import.js: Drag & Drop Upload
- static/css/style.css: Dark Theme, DM Mono + Syne Fonts
CSS Vars: --bg #0d0f14, --surface, --surface2, --border, --text, --muted, --accent #f0a500

API ENDPUNKTE:
- GET /api/transactions/summary -> [{month, income, expenses, net, tx_count}]
- GET /api/transactions/categories?month=2026-01 -> [{category, total}]
- GET /api/transactions/months -> ["2026-01",...]
- GET /api/reports/trends?months=6 -> {months:[...], series:[{category, values:[...]}]}
- GET /api/etf/positions -> [{isin, name, total_invested, current_value, gain_eur, gain_pct,...}]
- POST /api/etf/positions mit URLSearchParams: isin, name, wkn, ticker, monthly_amount

AUFGABEN:

1. ROBUSTHEIT bei leerer DB:
   Alle apiFetch() Calls in try/catch einwickeln.
   Leere months: KPI-Cards zeigen Bindestrich, Charts leere States.
   Kein uncaught TypeError wenn API-Arrays leer sind.

2. ETF-View — Position hinzufueigen:
   In index.html neuen Card-Bereich im ETF-View:
   Felder ISIN, Name, Ticker (optional), Sparplan EUR/Monat (optional).
   Button "Hinzufuegen" ruft POST /api/etf/positions auf.
   Nach Erfolg: Formular leeren, Positionen neu laden.
   Fehler anzeigen bei doppelter ISIN.
   Styling mit .card, .text-input, .btn-primary.

3. Import-View — Ergebnis verbessern:
   Nach Upload: statt rohem JSON eine lesbare Zusammenfassung:
   Anzahl importierte Transaktionen, ETF-Kaeufe, uebersprungene, Kontoauszug-Label.
   Mit klaren Icons/Farben, kein raw JSON.

4. Trends-Chart verdrahten:
   renderTrendChart() soll /api/reports/trends?months=6 aufrufen.
   Bei Fehler/404: "Trends werden geladen..." anzeigen, kein Crash.
   Bei Erfolg: Chart.js Liniendiagramm, eine Linie pro Kategorie.

5. DESIGN POLISHING:
   Lade-Indikatoren bei API-Calls (Button deaktivieren, Loading-Text).
   Empty States mit Text statt leerer Flaechen.
   KPI-Karten, Tabellen, ETF-Cards visuell aufwerten wo sinnvoll.
   Dark Theme und Fonts bleiben unveraendert.

6. Weitere UX-Verbesserungen die dir auffallen: eigenstaendig umsetzen.

Schreibe am Ende eine Zusammenfassung aller Aenderungen.
EOF

tmux send-keys -t "$SESSION:0.2" "claude --dangerously-skip-permissions -p \"$PROMPT_UI\"" Enter

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  finanztracker-dev gestartet"
echo "  Pane 0 oben links:  backend-quality"
echo "  Pane 1 oben rechts: backend-features"
echo "  Pane 2 unten:       frontend"
echo "  Ctrl+b d  = Session verlassen (Agenten laufen weiter)"
echo "  Ctrl+b z  = Pane maximieren/zurueck"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

tmux attach-session -t "$SESSION"
