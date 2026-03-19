// app.js – Main controller (ES module)
import { initCharts, renderBarChart, renderDonutChart, renderTrendChart, renderEtfHistoryChart } from './charts.js';
import { initImport } from './import.js';
import { loadEtfView } from './etf.js';

const API = '';  // same origin

export const CAT_COLORS = {
  'Lebensmittel':      '#f0a500',
  'Lieferando':        '#e05a7a',
  'Restaurant/Café':   '#c084fc',
  'Amazon':            '#3d9cf5',
  'Streaming':         '#34d399',
  'Gaming':            '#fb7185',
  'Versicherung':      '#94a3b8',
  'Kredit & Schulden': '#f97316',
  'Investments':       '#22d3ee',
  'Transport & Auto':  '#a3e635',
  'Gesundheit':        '#f472b6',
  'Sonstiges':         '#9ca3af',
  'Einnahmen':         '#4ade80',
};

// ── State ──────────────────────────────────────────────
let months = [];
let currentMonthIdx = -1;  // -1 = all
let allCategories = [];
let txPage = 0;
const TX_PAGE_SIZE = 50;
let editingTxId = null;
let allTransactions = [];

// ── Utils ──────────────────────────────────────────────
export function makeEmptyState(text) {
  const div = document.createElement('div');
  div.className = 'empty-state';
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '1.5');
  const path1 = document.createElementNS(ns, 'path');
  path1.setAttribute('d', 'M3 3v18h18');
  const path2 = document.createElementNS(ns, 'path');
  path2.setAttribute('d', 'M18 9l-5-5-4 4-3-3');
  svg.appendChild(path1);
  svg.appendChild(path2);
  const p = document.createElement('p');
  p.textContent = text;
  div.appendChild(svg);
  div.appendChild(p);
  return div;
}

export function fmtEur(n, signed = false) {
  const abs = Math.abs(n).toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (signed) return (n >= 0 ? '+' : '−') + abs + ' €';
  return (n < 0 ? '−' : '') + abs + ' €';
}

export function fmtDate(s) {
  if (!s) return '';
  const d = new Date(s);
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

async function apiFetch(path, opts = {}) {
  const res = await fetch(API + path, opts);
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.json();
}

export { apiFetch };

// ── Navigation ─────────────────────────────────────────
document.querySelectorAll('.nav-link').forEach(link => {
  link.addEventListener('click', e => {
    e.preventDefault();
    const view = link.dataset.view;
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    link.classList.add('active');
    document.getElementById(`view-${view}`).classList.add('active');
    if (view === 'etf') loadEtfView();
    if (view === 'transactions') loadTransactions();
    if (view === 'import') loadImportHistory();
  });
});

// ── Health check ───────────────────────────────────────
async function checkApi() {
  const dot  = document.querySelector('.status-dot');
  const text = document.querySelector('.status-text');
  try {
    await apiFetch('/health');
    dot.className  = 'status-dot online';
    text.textContent = 'Online';
  } catch {
    dot.className  = 'status-dot offline';
    text.textContent = 'Offline';
  }
}

// ── Month navigation ───────────────────────────────────
async function loadMonths() {
  try {
    months = await apiFetch('/api/transactions/months');
  } catch { months = []; }
  updateMonthLabel();
}

function currentMonth() {
  return currentMonthIdx >= 0 ? months[currentMonthIdx] : null;
}

function updateMonthLabel() {
  const label = document.getElementById('monthLabel');
  const m = currentMonth();
  if (!m) { label.textContent = 'Gesamt'; return; }
  const [y, mo] = m.split('-');
  const names = ['Jan','Feb','Mär','Apr','Mai','Jun','Jul','Aug','Sep','Okt','Nov','Dez'];
  label.textContent = `${names[parseInt(mo)-1]} ${y}`;
}

document.getElementById('monthPrev').addEventListener('click', () => {
  if (currentMonthIdx < months.length - 1) currentMonthIdx++;
  else currentMonthIdx = -1;
  updateMonthLabel();
  loadDashboard();
});

document.getElementById('monthNext').addEventListener('click', () => {
  if (currentMonthIdx === -1) currentMonthIdx = 0;
  else if (currentMonthIdx > 0) currentMonthIdx--;
  updateMonthLabel();
  loadDashboard();
});

document.getElementById('monthAll').addEventListener('click', () => {
  currentMonthIdx = -1;
  updateMonthLabel();
  loadDashboard();
});

// ── Dashboard ──────────────────────────────────────────
async function loadDashboard() {
  const m = currentMonth();
  const params = m ? `?month=${m}` : '';

  try {
    const [summary, catBreakdown, allSummary] = await Promise.all([
      apiFetch(`/api/transactions/summary`),
      apiFetch(`/api/transactions/categories${params}`),
      apiFetch(`/api/transactions/summary`),
    ]);

    // KPIs – show dash when no data
    if (!summary.length) {
      ['kpiOut','kpiIn','kpiNet','kpiSavings'].forEach(id => {
        document.getElementById(id).textContent = '–';
      });
      document.getElementById('kpiNet').className = 'kpi-value';
      ['kpiOutSub','kpiInSub','kpiSavingsSub','kpiNetSub'].forEach(id => {
        const el = document.getElementById(id);
        el.textContent = '';
        el.className = 'kpi-sub';
      });
    } else {
      let income = 0, expenses = 0;
      if (m) {
        const row = summary.find(s => s.month === m);
        if (row) { income = row.income; expenses = row.expenses; }
      } else {
        summary.forEach(s => { income += s.income; expenses += s.expenses; });
      }

      const net     = income - expenses;
      const savings = income > 0 ? ((income - expenses) / income * 100) : 0;

      document.getElementById('kpiOut').textContent  = '−' + fmtEur(expenses);
      document.getElementById('kpiIn').textContent   = '+' + fmtEur(income);
      document.getElementById('kpiNet').textContent  = fmtEur(net, true);
      document.getElementById('kpiNet').className    = 'kpi-value ' + (net >= 0 ? 'positive' : 'negative');
      document.getElementById('kpiSavings').textContent = savings.toFixed(1) + '%';

      const months_count = m ? 1 : (summary.length || 1);
      if (m) {
        // Show month-over-month delta vs previous month
        const mIdx = summary.findIndex(s => s.month === m);
        const prev = mIdx > 0 ? summary[mIdx - 1] : null;
        if (prev) {
          const outDelta = prev.expenses > 0 ? ((expenses - prev.expenses) / prev.expenses * 100) : 0;
          const inDelta  = prev.income  > 0 ? ((income  - prev.income)  / prev.income  * 100) : 0;
          const prevNet  = prev.income - prev.expenses;
          const outSubEl = document.getElementById('kpiOutSub');
          const inSubEl  = document.getElementById('kpiInSub');
          const savSubEl = document.getElementById('kpiSavingsSub');
          const netSubEl = document.getElementById('kpiNetSub');
          // Ausgaben: lower is better → invert color logic
          outSubEl.textContent = `${outDelta >= 0 ? '+' : ''}${outDelta.toFixed(1)}% ggü. Vormonat`;
          outSubEl.className   = 'kpi-sub ' + (outDelta <= 0 ? 'positive' : 'negative');
          inSubEl.textContent  = `${inDelta  >= 0 ? '+' : ''}${inDelta.toFixed(1)}% ggü. Vormonat`;
          inSubEl.className    = 'kpi-sub ' + (inDelta  >= 0 ? 'positive' : 'negative');
          const savDelta = prev.income > 0
            ? (savings - ((prev.income - prev.expenses) / prev.income * 100))
            : 0;
          savSubEl.textContent = `${savDelta >= 0 ? '+' : ''}${savDelta.toFixed(1)}pp ggü. Vormonat`;
          savSubEl.className   = 'kpi-sub ' + (savDelta >= 0 ? 'positive' : 'negative');
          netSubEl.textContent = `Vormonat: ${fmtEur(prevNet, true)}`;
          netSubEl.className   = 'kpi-sub';
        } else {
          ['kpiOutSub','kpiInSub','kpiSavingsSub','kpiNetSub'].forEach(id => {
            const el = document.getElementById(id);
            el.textContent = '';
            el.className = 'kpi-sub';
          });
        }
      } else {
        const outSubEl = document.getElementById('kpiOutSub');
        const inSubEl  = document.getElementById('kpiInSub');
        const savSubEl = document.getElementById('kpiSavingsSub');
        const netSubEl = document.getElementById('kpiNetSub');
        outSubEl.textContent = `Ø ${fmtEur(expenses / months_count)} / Monat`;
        outSubEl.className   = 'kpi-sub';
        inSubEl.textContent  = `Ø ${fmtEur(income  / months_count)} / Monat`;
        inSubEl.className    = 'kpi-sub';
        savSubEl.textContent = `${summary.length} Monate Daten`;
        savSubEl.className   = 'kpi-sub';
        netSubEl.textContent = `Ø ${fmtEur(net / months_count)} / Monat`;
        netSubEl.className   = 'kpi-sub';
      }
    }

    // Category bars
    const catBars = document.getElementById('catBars');
    const expCats = (catBreakdown || []).filter(c => c.category !== 'Einnahmen');
    const maxVal  = expCats[0]?.total || 1;

    if (!expCats.length) {
      catBars.textContent = '';
      catBars.appendChild(makeEmptyState('Keine Kategoriedaten'));
    } else {
      catBars.innerHTML = expCats.slice(0, 12).map(c => `
        <div class="cat-row">
          <div class="cat-name">${c.category}</div>
          <div class="cat-bar-wrap">
            <div class="cat-bar" style="width:${(c.total/maxVal*100).toFixed(1)}%;background:${CAT_COLORS[c.category]||'#888'}"></div>
          </div>
          <div class="cat-amount">${fmtEur(c.total)}</div>
        </div>
      `).join('');
    }

    // Charts
    renderBarChart(allSummary);
    renderDonutChart(expCats);
    renderTrendChart();

    // Donut legend
    const legend = document.getElementById('donutLegend');
    if (!expCats.length) {
      legend.textContent = '';
    } else {
      legend.innerHTML = expCats.slice(0, 8).map(c => `
        <div class="legend-item">
          <div class="legend-dot" style="background:${CAT_COLORS[c.category]||'#888'}"></div>
          <span>${c.category}</span>
        </div>
      `).join('');
    }

  } catch(e) {
    console.error('Dashboard error:', e);
  }
}

// ── Transactions ───────────────────────────────────────
async function loadTransactions() {
  const month = document.getElementById('txFilterMonth').value;
  const cat   = document.getElementById('txFilterCat').value;
  const search = document.getElementById('txSearch').value.toLowerCase();

  try {
    const params = new URLSearchParams({ limit: 1000 });
    if (month) params.set('month', month);
    if (cat)   params.set('category', cat);

    allTransactions = await apiFetch(`/api/transactions?${params}`);

    let filtered = allTransactions;
    if (search) {
      filtered = filtered.filter(t =>
        t.merchant.toLowerCase().includes(search) ||
        t.description.toLowerCase().includes(search)
      );
    }

    renderTxTable(filtered, txPage);
    renderPagination(filtered.length);
  } catch(e) {
    console.error('Transactions error:', e);
  }
}

function renderTxTable(txs, page) {
  const start = page * TX_PAGE_SIZE;
  const slice = txs.slice(start, start + TX_PAGE_SIZE);
  const tbody = document.getElementById('txBody');

  if (!slice.length) {
    tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state">Keine Transaktionen gefunden</div></td></tr>`;
    return;
  }

  tbody.innerHTML = slice.map(tx => {
    const color = CAT_COLORS[tx.category] || '#888';
    const badge = `<span class="badge" style="background:${color}22;color:${color}" onclick="openCatModal(${tx.id},'${escHtml(tx.merchant)}','${tx.category}')">${tx.category}</span>`;
    return `<tr>
      <td class="muted">${fmtDate(tx.date)}</td>
      <td>${escHtml(tx.merchant)}</td>
      <td class="tx-desc muted" title="${escHtml(tx.description)}">${escHtml(tx.description.slice(0,60))}${tx.description.length > 60 ? '<span class="tx-desc-ellipsis">…</span>' : ''}</td>
      <td>${badge}</td>
      <td class="right ${tx.amount < 0 ? 'negative' : 'positive'}">${fmtEur(tx.amount, true)}</td>
    </tr>`;
  }).join('');
}

function renderPagination(total) {
  const pages = Math.ceil(total / TX_PAGE_SIZE);
  const pg = document.getElementById('txPagination');
  if (pages <= 1) { pg.innerHTML = ''; return; }
  pg.innerHTML = Array.from({length: pages}, (_, i) =>
    `<button class="page-btn ${i===txPage?'active':''}" onclick="setTxPage(${i})">${i+1}</button>`
  ).join('');
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

window.setTxPage = function(page) {
  txPage = page;
  let filtered = allTransactions;
  const search = document.getElementById('txSearch').value.toLowerCase();
  if (search) filtered = filtered.filter(t => t.merchant.toLowerCase().includes(search) || t.description.toLowerCase().includes(search));
  renderTxTable(filtered, page);
  renderPagination(filtered.length);
};

// Populate filter dropdowns
async function populateFilters() {
  try {
    const [txMonths, cats] = await Promise.all([
      apiFetch('/api/transactions/months'),
      apiFetch('/api/transactions/categories/list'),
    ]);
    allCategories = cats;

    const monthSel = document.getElementById('txFilterMonth');
    txMonths.forEach(m => {
      const [y, mo] = m.split('-');
      const names = ['Jan','Feb','Mär','Apr','Mai','Jun','Jul','Aug','Sep','Okt','Nov','Dez'];
      const opt = new Option(`${names[parseInt(mo)-1]} ${y}`, m);
      monthSel.appendChild(opt);
    });

    const catSel = document.getElementById('txFilterCat');
    cats.forEach(c => catSel.appendChild(new Option(c, c)));

    // Modal select
    const modalSel = document.getElementById('catModalSelect');
    cats.forEach(c => modalSel.appendChild(new Option(c, c)));
  } catch(e) { console.error(e); }
}

['txFilterMonth','txFilterCat'].forEach(id =>
  document.getElementById(id).addEventListener('change', () => { txPage = 0; loadTransactions(); })
);
document.getElementById('txSearch').addEventListener('input', () => { txPage = 0; loadTransactions(); });

// ── Category modal ─────────────────────────────────────
window.openCatModal = function(id, merchant, currentCat) {
  editingTxId = id;
  document.getElementById('catModalDesc').textContent = merchant;
  document.getElementById('catModalSelect').value = currentCat;
  document.getElementById('catModal').style.display = 'flex';
};

document.getElementById('catModalClose').addEventListener('click',  () => document.getElementById('catModal').style.display = 'none');
document.getElementById('catModalCancel').addEventListener('click', () => document.getElementById('catModal').style.display = 'none');

document.getElementById('catModalSave').addEventListener('click', async () => {
  const cat = document.getElementById('catModalSelect').value;
  try {
    await apiFetch(`/api/transactions/${editingTxId}/category`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category: cat }),
    });
    document.getElementById('catModal').style.display = 'none';
    loadTransactions();
    loadDashboard();
  } catch(e) { alert('Fehler beim Speichern: ' + e.message); }
});

// ── Import history ──────────────────────────────────────
async function loadImportHistory() {
  try {
    const summary = await apiFetch('/api/transactions/summary');
    const hist = document.getElementById('importHistory');
    if (!summary.length) {
      hist.innerHTML = '<div class="empty-state">Noch keine Auszüge importiert</div>';
      return;
    }
    hist.innerHTML = `
      <table class="data-table">
        <thead><tr><th>Monat</th><th class="right">Ausgaben</th><th class="right">Einnahmen</th><th class="right">Transaktionen</th></tr></thead>
        <tbody>
          ${summary.map(s => `<tr>
            <td>${s.month}</td>
            <td class="right negative">−${fmtEur(s.expenses)}</td>
            <td class="right positive">+${fmtEur(s.income)}</td>
            <td class="right muted">${s.tx_count}</td>
          </tr>`).join('')}
        </tbody>
      </table>`;
  } catch(e) { console.error(e); }
}

// ── Init ───────────────────────────────────────────────
async function init() {
  initCharts();
  initImport(loadDashboard, loadImportHistory);
  await checkApi();
  await loadMonths();
  await populateFilters();
  await loadDashboard();
}

init();
