# Parallel Code Review via tmux + Agent Teams — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `./tmux-dev.sh` startet eine tmux-Session mit drei parallelen Claude-Agenten, die eigenständig Backend-Qualität, fehlende Backend-Features und Frontend-Modernisierung des Finanztracker durchführen.

**Architecture:** Ein Bash-Script erstellt eine tmux-Session mit drei Panes und startet in jedem Pane einen `claude`-Agenten mit präzisem, self-contained Prompt. Die Agenten arbeiten parallel auf strikt getrennten Datei-Domänen. Kein Server-Pane — FastAPI läuft separat.

**Tech Stack:** tmux, claude CLI, FastAPI, SQLModel, APScheduler 3.10, Chart.js, Vanilla JS ES Modules

---

## File Map

| Datei | Aktion | Agent |
|-------|--------|-------|
| `tmux-dev.sh` | Erstellt (bereits auf Disk) | — |
| `backend/routers/reports.py` | Neu erstellen | Agent 2 |
| `backend/services/scheduler.py` | Neu erstellen | Agent 2 |
| `backend/main.py` | Ändern: Router + Scheduler in lifespan | Agent 2 |
| `backend/services/pdf_parser.py` | BinaryIO Hint, statement_label nutzen | Agent 1 |
| `backend/routers/transactions.py` | Top-Level Imports, SQL Aggregation | Agent 1 |
| `backend/routers/etf.py` | Annotated Depends, 409 bei doppelter ISIN | Agent 1 |
| `backend/models/transaction.py` | account_statement Feld in ParsedTransaction | Agent 1 |
| `frontend/index.html` | ETF-Formular Section | Agent 3 |
| `frontend/static/js/app.js` | Robustheit, Trends-Chart | Agent 3 |
| `frontend/static/js/etf.js` | Position hinzufügen | Agent 3 |
| `frontend/static/js/import.js` | Ergebnis-Darstellung | Agent 3 |
| `frontend/static/css/style.css` | Design-Polishing | Agent 3 |
| `tasks/todo.md` | Checkboxen aktualisieren | Agent 2 |

---

## Task 1: Vorbereitung prüfen

**Files:** `tmux-dev.sh` (bereits erstellt)

- [ ] **Schritt 1.1: Abhängigkeiten prüfen**

```bash
which tmux && tmux -V
which claude && claude --version
```

Erwartung: tmux >= 3.0, claude CLI verfügbar. Falls claude fehlt: per npm oder brew installieren.

- [ ] **Schritt 1.2: tmux-Layout testen (ohne Agenten)**

```bash
tmux new-session -d -s ft-test -x 240 -y 60
tmux split-window -h -t ft-test:0
tmux split-window -v -t ft-test:0.0
tmux select-layout -t ft-test:0 main-vertical
tmux display-panes -t ft-test
tmux kill-session -t ft-test
```

Erwartung: Pane IDs 0, 1, 2 sichtbar, kein Fehler.

- [ ] **Schritt 1.3: Script-Rechte prüfen**

```bash
ls -la /Users/christian/Programmieren/finanztracker/tmux-dev.sh
```

Erwartung: `-rwxr-xr-x` (ausführbar). Falls nicht: `chmod +x tmux-dev.sh`

- [ ] **Schritt 1.4: Commit**

```bash
cd /Users/christian/Programmieren/finanztracker
git add tmux-dev.sh docs/
git commit -m "feat: add tmux-dev.sh for parallel agent sessions"
```

---

## Task 2: Agenten starten

- [ ] **Schritt 2.1: Session starten**

```bash
cd /Users/christian/Programmieren/finanztracker
./tmux-dev.sh
```

Du siehst drei Panes — alle drei Agenten starten automatisch.

**tmux Navigation:**

| Shortcut | Aktion |
|----------|--------|
| `Ctrl+b →` / `←` | Zwischen Panes wechseln |
| `Ctrl+b z` | Aktuelles Pane maximieren / zurück |
| `Ctrl+b d` | Session verlassen (Agenten laufen weiter) |
| `tmux attach -t finanztracker-dev` | Wieder einsteigen |

- [ ] **Schritt 2.2: Agenten laufen lassen**

Kein Eingriff nötig. Alle drei Agenten arbeiten autonom.
Jeder gibt laufend Fortschritt aus und endet mit einer Zusammenfassung.

---

## Task 3: Ergebnisse reviewen und testen

- [ ] **Schritt 3.1: Geänderte Dateien reviewen**

```bash
cd /Users/christian/Programmieren/finanztracker
git diff --stat
```

Erwartung: ca. 8-12 geänderte/neue Dateien verteilt auf alle drei Domänen.

- [ ] **Schritt 3.2: Python-Umgebung aufsetzen (falls noch nicht vorhanden)**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Schritt 3.3: Backend starten und API prüfen**

```bash
export DB_PATH=./data/finanztracker.db
mkdir -p data
uvicorn backend.main:app --reload --port 8080
```

Browser: http://localhost:8080/docs

Checkliste:
- [ ] `/api/reports/monthly/{year}/{month}` erscheint in Swagger
- [ ] `/api/reports/trends` erscheint in Swagger
- [ ] `/api/transactions/summary` antwortet (auch bei leerer DB)
- [ ] Kein Import-Fehler beim Start

- [ ] **Schritt 3.4: Frontend prüfen**

Browser: http://localhost:8080

Checkliste:
- [ ] Dashboard lädt ohne JS-Fehler (auch bei leerer DB — Browser-Konsole prüfen)
- [ ] ETF-Tab: "Position hinzufügen"-Formular sichtbar
- [ ] Import-Tab: Upload-Ergebnis zeigt lesbare Zusammenfassung (nicht raw JSON)
- [ ] Trends-Chart: zeigt Lade-State oder Daten (kein Crash)
- [ ] Keine uncaught Errors in Browser-Konsole (F12)

- [ ] **Schritt 3.5: Scheduler prüfen**

In den Server-Logs (Terminal mit uvicorn) nach APScheduler-Meldung suchen:

```
INFO - APScheduler started
INFO - Adding job "refresh_prices_daily"
```

- [ ] **Schritt 3.6: Abschluss-Commit**

```bash
git add -A
git commit -m "feat: parallel agent review — backend quality, reports, frontend modernization"
```

---

## Bekannte Risiken

| Risiko | Mitigation |
|--------|-----------|
| Agent 3 ruft `/api/reports/trends` auf, der noch nicht existiert | Prompt enthält Fehlerbehandlung bei 404 |
| `main.py` Konflikte | Agent 1 fasst `main.py` nicht an (explizit verboten) |
| claude CLI nicht installiert | Schritt 1.1 prüft vorab |
| Agent läuft in Endlosschleife | `Ctrl+b x` — Pane schließen |
| tmux-Layout unlesbar auf kleinem Terminal | Fenster auf mind. 240x60 vergrößern |
