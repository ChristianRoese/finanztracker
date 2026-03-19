# Design: Parallel Code Review via tmux + Agent Teams

**Datum:** 2026-03-19
**Status:** Approved

---

## Ziel

Den gesamten Finanztracker-Code (Backend, Features, Frontend) durch drei parallel laufende Claude-Agenten reviewen, korrigieren und modernisieren lassen. Die Agenten laufen in einem tmux-Session sichtbar in separaten Panes. Ein einzelnes Script `./tmux-dev.sh` startet alles vollautomatisch.

---

## tmux-Architektur

```
Session: finanztracker-dev
+------------------+----------------------------------+
|  Pane 0          |  Pane 1                          |
|  [backend-       |  [backend-                       |
|   quality]       |   features]                      |
+------------------+----------------------------------+
|  Pane 2                                             |
|  [frontend]                                         |
+-----------------------------------------------------+
```

- Layout: Pane 0+1 oben nebeneinander, Pane 2 unten als Full-Width
- Jeder Agent läuft mit `claude --dangerously-skip-permissions -p "<prompt>"`
- Kein Server-Pane (App läuft separat/in Docker)

---

## Agent 1: `backend-quality`

**Scope:** `backend/routers/`, `backend/services/`, `backend/models/`, `backend/database.py`
**Verboten:** Keine neuen Features; `backend/main.py` NICHT anfassen (gehört Agent 2)

**Konkrete Aufgaben:**
1. `pdf_parser.py`: `statement_label`-Parameter wird übergeben aber intern nie genutzt → in `ParsedTransaction` als Feld übernehmen und im Hash-Schlüssel verwenden, damit Duplikat-Erkennung pro Kontoauszug funktioniert
2. `pdf_parser.py`: Type hint `file_bytes: bytes` ist falsch (Router übergibt `io.BytesIO`) → auf `BinaryIO` aus `typing` korrigieren
3. `routers/transactions.py`: `HTTPException`-Import innerhalb von Funktionskörpern → Top-Level-Import
4. `routers/etf.py`: `create_position` nutzt inkonsistentes Depends-Pattern ohne `Annotated`
5. `routers/transactions.py`: `monthly_summary` lädt alle Transaktionen in Memory → SQL-Aggregation mit `func.sum`, `func.count`, `group_by`
6. Type hints vervollständigen wo sie inkonsistent oder fehlend sind
7. Agenten-Freiheit: weitere Qualitätsprobleme eigenständig beheben

---

## Agent 2: `backend-features`

**Scope:** neue Dateien `backend/routers/reports.py`, `backend/services/scheduler.py`; Änderungen an `backend/main.py`, `backend/services/etf_service.py`
**Verboten:** Keine Änderungen an `routers/transactions.py`, `routers/etf.py`, `models/`

**Konkrete Aufgaben:**
1. `routers/reports.py` implementieren:
   - `GET /api/reports/monthly/{year}/{month}` - Monatsbericht mit Kategorie-Breakdown
   - `GET /api/reports/trends` - Ausgaben pro Kategorie über die letzten N Monate
2. `services/scheduler.py` implementieren: APScheduler-Job der täglich `refresh_all_prices` aufruft (APScheduler ist bereits in `requirements.txt`)
3. `main.py`: Router + Scheduler in `lifespan` registrieren — Agent 2 ist alleiniger Owner von `main.py`
4. `tasks/todo.md`: Sprint-Checkboxen auf abgehakt setzen wo Code bereits existiert
5. Agenten-Freiheit: weitere sinnvolle Backend-Features

---

## Agent 3: `frontend`

**Scope:** `frontend/` (alle Dateien)
**Verboten:** Keine Backend-Änderungen

**Konkrete Aufgaben:**
1. Trends-Chart: `/api/reports/trends` ansprechen — da Agent 2 parallel läuft und der Endpunkt noch nicht existiert, zunächst als funktionalen Stub implementieren (Chart-Rendering-Code fertig, API-Call mit Fehlerbehandlung wenn 404)
2. Robustheit bei leerer DB: kein JS-Crash wenn `months` leer, alle async-Calls in try/catch
3. ETF-View: "Position hinzufügen"-Formular implementieren (`POST /api/etf/positions`)
4. Import-View: Ergebnis nach Upload klarer darstellen (importierte vs. skipped Transaktionen)
5. Frontend-Design: visuell polieren (Spacing, leere Zustände, Lade-Indikatoren)
6. Agenten-Freiheit: weitere UX-Verbesserungen, Frontend-Design-Skill verwenden

---

## tmux-Dev-Script

`./tmux-dev.sh`:
- Session anlegen (bestehende killen)
- Drei Panes aufteilen im beschriebenen Layout
- Jeden Agenten mit präzisem Scope-Prompt starten
- Session attachen

---

## Koordination

- Agenten arbeiten parallel, kein geteilter State, keine geteilten Dateien
- `main.py` gehört ausschließlich Agent 2 — Agent 1 fasst sie nicht an
- Agent 3 implementiert Trends-Chart als Stub (Fehlertoleranz wenn Endpunkt noch nicht existiert)
- Nach Abschluss: manueller Review, kein automatischer Merge

---

## Erfolgskriterien

- `./tmux-dev.sh` startet fehlerfrei, alle 3 Panes sichtbar
- Alle drei Agenten laufen durch ohne manuellen Eingriff
- Backend: kein toter Code, konsistente Patterns, SQL-Aggregation in summary
- Features: `/api/reports/*` antwortet, Scheduler registriert
- Frontend: kein JS-Crash bei leerer DB, ETF-Formular vorhanden, Trends-Chart lädt
