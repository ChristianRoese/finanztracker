// etf.js – ETF Portfolio View
import { apiFetch, fmtEur, fmtDate, makeEmptyState } from './app.js';
import { renderEtfHistoryChart, renderEtfForecastChart } from './charts.js';

export async function loadEtfView() {
  await Promise.all([loadEtfPositions(), loadEtfPurchases(), loadEtfForecast()]);

  // Add position form (attach once)
  const form = document.getElementById('etfAddForm');
  if (form && !form._bound) {
    form._bound = true;
    form.addEventListener('submit', async e => {
      e.preventDefault();
      const errEl = document.getElementById('etfAddError');
      errEl.style.display = 'none';

      const isin   = document.getElementById('etfAddIsin').value.trim();
      const name   = document.getElementById('etfAddName').value.trim();
      const wkn    = document.getElementById('etfAddWkn').value.trim();
      const ticker = document.getElementById('etfAddTicker').value.trim();
      const amount = parseFloat(document.getElementById('etfAddAmount').value) || 0;

      const btn = document.getElementById('etfAddBtn');
      btn.disabled = true;
      btn.textContent = 'Speichere…';

      try {
        await apiFetch('/api/etf/positions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ isin, name, wkn: wkn || undefined, ticker: ticker || undefined, monthly_amount: amount }),
        });
        form.reset();
        await loadEtfPositions();
        await loadEtfForecast();
      } catch(err) {
        errEl.textContent = err.message.includes('409') || err.message.includes('400')
          ? 'ISIN existiert bereits oder ungültige Eingabe.'
          : `Fehler: ${err.message}`;
        errEl.style.display = 'block';
      } finally {
        btn.disabled = false;
        btn.textContent = 'Hinzufügen';
      }
    });
  }

  document.getElementById('refreshPricesBtn').onclick = async () => {
    const btn = document.getElementById('refreshPricesBtn');
    btn.textContent = 'Aktualisiere…';
    btn.disabled = true;
    try {
      const res = await apiFetch('/api/etf/refresh-prices', { method: 'POST' });
      await loadEtfPositions();
      await loadEtfForecast();
      btn.textContent = `✓ ${res.count} Preise aktualisiert`;
    } catch(e) {
      btn.textContent = 'Fehler – erneut versuchen';
    }
    setTimeout(() => { btn.textContent = 'Preise aktualisieren'; btn.disabled = false; }, 3000);
  };
}

async function loadEtfPositions() {
  try {
    const positions = await apiFetch('/api/etf/positions');

    // KPIs (nur aktive Positionen)
    const active        = positions.filter(p => !p.fully_sold);
    const totalInvested = active.reduce((s,p) => s + p.total_invested, 0);
    const totalValue    = active.reduce((s,p) => s + p.current_value, 0);
    const totalGain     = totalValue - totalInvested;
    const totalGainPct  = totalInvested > 0 ? (totalGain / totalInvested * 100) : 0;

    document.getElementById('etfInvested').textContent = fmtEur(totalInvested);
    document.getElementById('etfValue').textContent    = fmtEur(totalValue);
    document.getElementById('etfGain').textContent     = fmtEur(totalGain, true);
    document.getElementById('etfGain').className       = 'kpi-value ' + (totalGain >= 0 ? 'positive' : 'negative');
    document.getElementById('etfPerf').textContent     = (totalGainPct >= 0 ? '+' : '') + totalGainPct.toFixed(2) + '%';
    document.getElementById('etfPerf').className       = 'kpi-value ' + (totalGainPct >= 0 ? 'positive' : 'negative');

    // Position cards
    const container = document.getElementById('etfPositions');
    if (!positions.length) {
      container.textContent = '';
      container.appendChild(makeEmptyState('Noch keine ETF-Positionen. PDF mit Wertpapierabrechnungen importieren.'));
      return;
    }

    container.innerHTML = positions.filter(p => !p.fully_sold).map(p => {
      const gainColor = p.fully_sold ? 'var(--muted)' : (p.gain_eur >= 0 ? 'var(--green)' : 'var(--red)');
      const gainSign  = p.gain_eur >= 0 ? '+' : '';
      const soldBadge = p.fully_sold ? '<span style="background:var(--muted);color:#000;font-size:0.65rem;padding:2px 6px;border-radius:4px;margin-left:6px">Vollständig verkauft</span>' : '';

      let cagrHtml = '';
      if (p.yearly_return_cagr != null) {
        const cagrColor = p.yearly_return_cagr >= 0 ? 'var(--green)' : 'var(--red)';
        const cagrSign  = p.yearly_return_cagr >= 0 ? '+' : '';
        const yearsLabel = p.years_held != null ? `${p.years_held.toFixed(1)} J.` : '';
        cagrHtml = `
          <div class="etf-meta-item">
            <div class="etf-meta-label">CAGR p.a. (${yearsLabel})</div>
            <div class="etf-meta-value" style="color:${cagrColor}">${cagrSign}${p.yearly_return_cagr.toFixed(2)}%</div>
          </div>`;
      }

      return `
        <div class="etf-position">
          <div class="etf-pos-header">
            <div>
              <div class="etf-pos-name">${p.name}${soldBadge}</div>
              <div class="etf-pos-isin">${p.isin} · ${p.wkn} · ${p.ticker || 'kein Ticker'}</div>
            </div>
            <div class="etf-pos-gain" style="color:${gainColor}">
              ${p.fully_sold ? '–' : `${gainSign}${fmtEur(p.gain_eur)} (${gainSign}${p.gain_pct.toFixed(2)}%)`}
            </div>
          </div>
          <div class="etf-pos-meta">
            <div class="etf-meta-item">
              <div class="etf-meta-label">Investiert</div>
              <div class="etf-meta-value">${fmtEur(p.total_invested)}</div>
            </div>
            <div class="etf-meta-item">
              <div class="etf-meta-label">Aktueller Wert</div>
              <div class="etf-meta-value" style="color:var(--accent2)">${fmtEur(p.current_value)}</div>
            </div>
            <div class="etf-meta-item">
              <div class="etf-meta-label">Ø Kaufpreis</div>
              <div class="etf-meta-value">${p.avg_buy_price.toFixed(4)} €</div>
            </div>
            <div class="etf-meta-item">
              <div class="etf-meta-label">Aktueller Kurs</div>
              <div class="etf-meta-value">${p.current_price.toFixed(4)} €</div>
            </div>
            <div class="etf-meta-item">
              <div class="etf-meta-label">Anteile</div>
              <div class="etf-meta-value">${p.total_shares.toFixed(4)}</div>
            </div>
            <div class="etf-meta-item">
              <div class="etf-meta-label">Käufe</div>
              <div class="etf-meta-value">${p.purchase_count}×</div>
            </div>
            <div class="etf-meta-item">
              <div class="etf-meta-label">Sparplan / Mo.</div>
              <div class="etf-meta-value">${fmtEur(p.monthly_amount)}</div>
            </div>
            ${cagrHtml}
            <div class="etf-meta-item">
              <div class="etf-meta-label">Kurs stand</div>
              <div class="etf-meta-value" style="color:var(--muted);font-size:0.65rem">${p.price_updated ? new Date(p.price_updated).toLocaleDateString('de-DE') : '–'}</div>
            </div>
          </div>
        </div>
      `;
    }).join('');

  } catch(e) {
    console.error('ETF positions error:', e);
  }
}

async function loadEtfForecast() {
  try {
    const data = await apiFetch('/api/etf/forecast');
    const card = document.getElementById('etfForecastCard');

    if (!data || !data.aggregate || data.aggregate.current_value === 0) {
      if (card) card.style.display = 'none';
      return;
    }
    if (card) card.style.display = '';

    renderEtfForecastChart(data.aggregate);

    // Fill table
    const tbody = document.getElementById('etfForecastBody');
    const { scenarios } = data.aggregate;
    tbody.innerHTML = data.years.map((yr, i) => {
      const best   = scenarios.best[i];
      const casual = scenarios.casual[i];
      const worst  = scenarios.worst[i];
      return `<tr>
        <td>Jahr ${yr}</td>
        <td class="right" style="color:var(--green)">${fmtEur(best)}</td>
        <td class="right" style="color:var(--accent2)">${fmtEur(casual)}</td>
        <td class="right" style="color:var(--red)">${fmtEur(worst)}</td>
      </tr>`;
    }).join('');

  } catch(e) {
    console.error('ETF forecast error:', e);
  }
}

async function loadEtfPurchases() {
  try {
    const purchases = await apiFetch('/api/etf/purchases');

    renderEtfHistoryChart(purchases, []);

    const tbody = document.getElementById('etfPurchaseBody');
    if (!purchases.length) {
      tbody.textContent = '';
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = 5;
      td.appendChild(makeEmptyState('Keine Käufe vorhanden'));
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }

    tbody.innerHTML = purchases.map(p => `
      <tr>
        <td>${fmtDate(p.date)}</td>
        <td>Position #${p.position_id}</td>
        <td>${p.price_eur.toFixed(4)} €</td>
        <td>${p.shares.toFixed(4)}</td>
        <td class="right accent">${fmtEur(p.total_eur)}</td>
      </tr>
    `).join('');

  } catch(e) {
    console.error('ETF purchases error:', e);
  }
}
