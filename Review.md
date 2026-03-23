# Finanztracker – Review-Ergebnisse

> Erstellt: 23.03.2026 | Code Review + Security Review via automatisiertem Agenten-Team

---

## Code Review

### Kritisch (müssen behoben werden)

- [ ] **XSS in `onclick`-Attributen** (`frontend/static/js/app.js:443, 573-574`)
  `escHtml()` escapet kein `'`. Merchant-Namen wie `McDonald's` können onclick-Attribute aufbrechen und JS-Injection ermöglichen.
  **Fix:** `'` → `&#39;` in `escHtml()` ergänzen, oder `data-*`-Attribute + Event-Delegation verwenden.

- [ ] **`except Exception: pass` in DB-Migration** (`backend/database.py:23-27`)
  Verschluckt alle Fehler (Disk Full, korrupte DB, Berechtigungsfehler), nicht nur "Spalte existiert bereits".
  **Fix:** Nur `OperationalError` mit `"duplicate column name"` unterdrücken, alles andere re-raisen.

- [ ] **N+1 Queries im Accounts-Router** (`backend/routers/accounts.py:26-43`)
  Pro Konto eine separate DB-Query statt ein einziger JOIN mit `group_by`.
  **Fix:** Einen aggregierten Query mit `func.count` + `group_by(BankAccount.id)` verwenden.

- [ ] **N+1 Queries im ETF-Service** (`backend/services/etf_service.py:226-249, 302-323`)
  `get_portfolio_summary` und `get_etf_forecast` feuern mindestens 15 Queries bei 5 Positionen.
  **Fix:** Alle Purchases/Prices in zwei Queries vorladen und per `position_id` in Python gruppieren.

### Mittel (sollten behoben werden)

- [ ] **Bug: ETF-Zähler im Frontend liest falschen Property-Namen** (`frontend/static/js/import.js:75`)
  Frontend liest `r.etf_purchases`, API liefert `imported_etf_purchases` → Zähler zeigt immer 0.

- [ ] **`datetime.utcnow()` deprecated seit Python 3.12** (`backend/models/transaction.py:34`, `account.py:11`, `etf.py:32`)
  **Fix:** Ersetzen durch `datetime.now(UTC)` mit `from datetime import UTC`.

- [ ] **Fehlende Query-Parameter-Validierung** (`backend/routers/transactions.py:15`, `reports.py:16-18`)
  `month` und `year` werden ohne Format-Validierung akzeptiert.
  **Fix:** `Query(None, pattern=r"^\d{4}-\d{2}$")` bzw. `r"^\d{4}$"` verwenden.

- [ ] **Anthropic-Client bei jedem Aufruf neu instanziiert** (`backend/services/categorizer.py:114`)
  **Fix:** Als Modul-Level-Singleton lazy initialisieren.

- [ ] **`import traceback, logging` innerhalb eines Catch-Blocks** (`backend/routers/import_.py:66`)
  **Fix:** Imports an den Dateianfang, Modul-Level-Logger verwenden.

- [ ] **`fully_sold`-Logik im Router statt im Service** (`backend/routers/import_.py:157-171`)
  Verstößt gegen "alle DB-Operationen in Services, nicht in Routers".
  **Fix:** In `update_fully_sold_flags(session)` im `etf_service.py` auslagern.

- [ ] **ETF-Kaufhistorie zeigt `Position #ID` statt ETF-Name** (`frontend/static/js/etf.js:216`)
  **Fix:** Backend-Endpoint um ETF-Namen erweitern oder Frontend cross-referenzieren.

- [ ] **Cascading-Problem beim Löschen von Auszügen** (`backend/routers/import_.py:213-225`)
  ETF-Purchases bleiben bestehen wenn ein Auszug gelöscht wird.

### Klein (nice to have)

- [ ] **Inkonsistente Toleranzwerte für "fully sold"**: `0.001` in `import_.py` vs. `0.0001` in `etf_service.py:260`
- [ ] **Fehlende DB-Indizes** auf `Transaction.month`, `Transaction.import_hash`, `ETFPrice.(position_id, date)`
- [ ] **Magic Numbers** in `etf_service.py`: `0.08` (= 30 Tage) und `0.001` (Toleranz) als benannte Konstanten
- [ ] **`form._bound` direkt auf DOM-Element** (`frontend/static/js/etf.js:10`) → Modul-Variable bevorzugen

---

## Security Review

### Kritisch (CVSS 7-10)

- [ ] **Keine Authentifizierung (CVSS 9.8)** (`backend/main.py`, alle Routers)
  Kein Endpunkt ist geschützt. Jeder im Netzwerk kann alle Daten lesen, manipulieren und löschen.
  **Fix:** Mindestens HTTP Basic Auth via nginx-Reverse-Proxy oder statischer API-Key als FastAPI-Dependency:
  ```python
  API_KEY = os.getenv("API_KEY")
  async def verify_key(credentials = Depends(HTTPBearer())):
      if credentials.credentials != API_KEY:
          raise HTTPException(401)
  ```

- [ ] **CORS zu permissiv (CVSS 8.1)** (`backend/main.py:25-30`)
  `allow_methods=["*"]` + `allow_headers=["*"]` ohne Einschränkung.
  **Fix:** `allow_methods=["GET","POST","PUT","DELETE"]`, `allow_headers=["Content-Type","Authorization"]`

- [ ] **PDF-Upload ohne Größenprüfung und Magic-Byte-Validierung (CVSS 7.5)** (`backend/routers/import_.py:59`)
  `file.read()` lädt alles in den RAM. Keine Prüfung auf echtes PDF-Format.
  **Fix:**
  ```python
  MAX_PDF_SIZE = 10 * 1024 * 1024
  content = await file.read(MAX_PDF_SIZE + 1)
  if len(content) > MAX_PDF_SIZE:
      raise HTTPException(413, "PDF zu groß (max. 10 MB)")
  if not content.startswith(b"%PDF"):
      raise HTTPException(400, "Keine gültige PDF-Datei")
  ```

- [ ] **Exception-Details im HTTP-Response (CVSS 7.3)** (`backend/routers/import_.py:68`)
  `f"PDF konnte nicht geparst werden: {e}"` leakt interne Pfade und Bibliotheksdetails.
  **Fix:** Generische Fehlermeldung an Client, Details nur ins Log.

### Mittel (CVSS 4-6)

- [ ] **Silent Failure in DB-Migration (CVSS 5.5)** – siehe Code-Review oben (`database.py:23-27`)

- [ ] **Zu breiter Exception-Catch im Categorizer (CVSS 5.0)** (`backend/services/categorizer.py:147`)
  `AuthenticationError` und `RateLimitError` werden gleich behandelt. Ungültiger API-Key kategorisiert still als "Sonstiges".
  **Fix:** Auf spezifische Anthropic-Fehlertypen aufteilen (`AuthenticationError` re-raisen).

- [ ] **SSRF via ISIN ohne Validierung (CVSS 5.3)** (`backend/services/etf_service.py:114`)
  ISIN wird ohne Format-Check direkt in Yahoo-Finance-URLs eingebettet.
  **Fix:** `re.compile(r"^[A-Z]{2}[A-Z0-9]{10}$")` vor URL-Verwendung prüfen.

- [ ] **Kein Subresource Integrity (SRI) für CDN-Ressourcen (CVSS 5.9)** (`frontend/index.html:7-8`)
  Chart.js von Cloudflare ohne `integrity`-Attribut.
  **Fix:** Chart.js lokal ablegen unter `frontend/static/js/vendor/` (empfohlen) oder SRI-Hash ergänzen.

- [ ] **XSS in onclick-Attributen (CVSS 5.4)** – identisch mit Code-Review-Fund (`app.js:443, 574`)

- [ ] **Volle IBAN im API-Response (CVSS 4.3)** (`backend/routers/accounts.py:38`)
  Kombiniert mit fehlendem Auth für alle im Netzwerk lesbar.
  **Fix:** Im Frontend maskiert anzeigen (z.B. `DE12 **** **** 7890`).

- [ ] **FX-Fallback auf 1.0 bei Fehler (CVSS 4.0)** (`backend/services/etf_service.py:87`)
  Bei Kurs-Abruf-Fehler wird USD-Preis als EUR-Preis gespeichert → Portfolio-Bewertung bis 15% falsch.
  **Fix:** `None` zurückgeben und Preis-Update für diese Position überspringen statt falschen Wert speichern.

### Niedrig (CVSS 1-3)

- [ ] **Docker läuft als root** (`Dockerfile`) – keinen `USER`-Befehl definiert
  **Fix:** `RUN adduser --system appuser && USER appuser`

- [ ] **Keine HTTP Security Headers** (`backend/main.py`)
  `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` fehlen.
  **Fix:** `SecurityHeadersMiddleware` als FastAPI-Middleware ergänzen.

- [ ] **Kein Rate Limiting auf PDF-Upload** – bei fehlendem Auth können unkontrolliert Claude-API-Kosten entstehen

- [ ] **Query-Parameter ohne Regex-Validierung** (`reports.py`, `transactions.py`) – siehe Code-Review oben

- [ ] **`pip-audit` nicht integriert** – `pip-audit -r requirements.txt` regelmäßig ausführen

---

## Prioritäten auf einen Blick

| Priorität | Was | Datei |
|-----------|-----|-------|
| 🔴 Sofort | Authentifizierung implementieren | `main.py` + alle Routers |
| 🔴 Sofort | PDF-Upload: Größe + Magic Bytes prüfen | `routers/import_.py:59` |
| 🔴 Sofort | `escHtml()` um `'`-Escaping ergänzen | `static/js/app.js:464` |
| 🔴 Sofort | Exception-Details nicht in HTTP-Response | `routers/import_.py:68` |
| 🟠 Kurzfristig | `except Exception: pass` in DB-Migration | `database.py:23-27` |
| 🟠 Kurzfristig | CORS einschränken | `main.py:25-30` |
| 🟠 Kurzfristig | ETF-Zähler-Bug im Frontend | `static/js/import.js:75` |
| 🟠 Kurzfristig | N+1 Queries eliminieren | `accounts.py`, `etf_service.py` |
| 🟠 Kurzfristig | FX-Fallback auf 1.0 korrigieren | `etf_service.py:87` |
| 🟡 Mittelfristig | SSRF via ISIN validieren | `etf_service.py:114` |
| 🟡 Mittelfristig | Chart.js lokal ablegen (SRI) | `index.html:7` |
| 🟡 Mittelfristig | `datetime.utcnow()` → `datetime.now(UTC)` | alle Models |
| 🟡 Mittelfristig | Security Headers Middleware | `main.py` |
| 🟡 Mittelfristig | Docker non-root User | `Dockerfile` |
