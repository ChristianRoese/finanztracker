// charts.js – Chart.js wrappers
import { apiFetch, CAT_COLORS, fmtEur } from './app.js';

let barChartInst      = null;
let donutChartInst    = null;
let trendChartInst    = null;
let etfHistoryInst    = null;
let etfForecastInst   = null;

const CHART_DEFAULTS = {
  backgroundColor: '#161b2e',
  borderColor: '#1f2640',
  titleColor: '#e2e6f0',
  bodyColor: '#7a8499',
};

function tooltipPlugin() {
  return {
    backgroundColor: CHART_DEFAULTS.backgroundColor,
    borderColor: CHART_DEFAULTS.borderColor,
    borderWidth: 1,
    titleColor: CHART_DEFAULTS.titleColor,
    bodyColor: CHART_DEFAULTS.bodyColor,
    padding: 12,
    cornerRadius: 2,
    titleFont: { family: 'IBM Plex Mono', size: 11, weight: '500' },
    bodyFont:  { family: 'IBM Plex Mono', size: 11 },
  };
}

function axisStyle() {
  return {
    ticks: { color: '#5a647a', font: { family: 'IBM Plex Mono', size: 10 } },
    grid: { color: '#1c2238' },
    border: { color: '#1f2640' },
  };
}

export function initCharts() {
  Chart.defaults.color = '#5a647a';
  Chart.defaults.font.family = 'IBM Plex Mono';
}

export function renderBarChart(allSummary, selectedYear = null, selectedMonth = null) {
  const ctx = document.getElementById('barChart');
  if (!ctx) return;

  if (!allSummary || !allSummary.length) {
    if (barChartInst) { barChartInst.destroy(); barChartInst = null; }
    ctx.style.display = 'none';
    const wrap = ctx.closest('.chart-wrap');
    if (wrap && !wrap.querySelector('.chart-empty')) {
      const d = document.createElement('div');
      d.className = 'chart-empty';
      d.textContent = 'Noch keine Daten';
      wrap.appendChild(d);
    }
    return;
  }
  ctx.style.display = '';
  const wrap = ctx.closest('.chart-wrap');
  const emp = wrap && wrap.querySelector('.chart-empty');
  if (emp) emp.remove();

  let recent;
  if (selectedYear && selectedMonth) {
    // Spezifischer Monat: zeige 3 Monate davor + gewählter + 2 danach (6 gesamt, zentriert)
    const target = `${selectedYear}-${selectedMonth}`;
    const idx = allSummary.findIndex(s => s.month === target);
    if (idx >= 0) {
      const from = Math.max(0, idx - 3);
      const to   = Math.min(allSummary.length, from + 6);
      recent = allSummary.slice(Math.max(0, to - 6), to);
    } else {
      recent = allSummary.slice(-6);
    }
  } else if (selectedYear) {
    // Nur Jahr: alle Monate des Jahres
    recent = allSummary.filter(s => s.month.startsWith(selectedYear));
  } else {
    // Kein Filter: letzte 6 Monate
    recent = allSummary.slice(-6);
  }
  const labels  = recent.map(s => {
    const [y, m] = s.month.split('-');
    const names = ['Jan','Feb','Mär','Apr','Mai','Jun','Jul','Aug','Sep','Okt','Nov','Dez'];
    return `${names[parseInt(m)-1]} ${y.slice(2)}`;
  });

  if (barChartInst) barChartInst.destroy();
  barChartInst = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Ausgaben',
          data: recent.map(s => s.expenses),
          backgroundColor: 'rgba(224, 90, 106, 0.75)',
          borderRadius: 2,
        },
        {
          label: 'Einnahmen',
          data: recent.map(s => s.income),
          backgroundColor: 'rgba(61, 207, 142, 0.75)',
          borderRadius: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: 'bottom',
          labels: { color: '#5a647a', font: { family: 'IBM Plex Mono', size: 10 }, boxWidth: 8, padding: 14 },
        },
        tooltip: {
          ...tooltipPlugin(),
          callbacks: { label: ctx => ` ${ctx.dataset.label}: ${fmtEur(ctx.parsed.y)}` },
        },
      },
      scales: {
        x: { ...axisStyle(), grid: { display: false } },
        y: { ...axisStyle(), ticks: { ...axisStyle().ticks, callback: v => v + '€' } },
      },
    },
  });
}

export function renderDonutChart(catBreakdown) {
  const ctx = document.getElementById('donutChart');
  if (!ctx) return;

  if (!catBreakdown || !catBreakdown.length) {
    if (donutChartInst) { donutChartInst.destroy(); donutChartInst = null; }
    ctx.style.display = 'none';
    const wrap = ctx.closest('.chart-wrap');
    if (wrap && !wrap.querySelector('.chart-empty')) {
      const d = document.createElement('div');
      d.className = 'chart-empty';
      d.textContent = 'Keine Kategoriedaten';
      wrap.appendChild(d);
    }
    return;
  }
  ctx.style.display = '';
  const wrap = ctx.closest('.chart-wrap');
  const emp = wrap && wrap.querySelector('.chart-empty');
  if (emp) emp.remove();

  const top8   = catBreakdown.slice(0, 8);
  const labels = top8.map(c => c.category);
  const data   = top8.map(c => c.total);
  const colors = top8.map(c => CAT_COLORS[c.category] || '#888');

  if (donutChartInst) donutChartInst.destroy();
  donutChartInst = new Chart(ctx, {
    type: 'doughnut',
    data: { labels, datasets: [{ data, backgroundColor: colors, borderWidth: 0, hoverOffset: 4 }] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '68%',
      plugins: {
        legend: { display: false },
        tooltip: {
          ...tooltipPlugin(),
          callbacks: { label: ctx => ` ${fmtEur(ctx.parsed)}` },
        },
      },
    },
  });
}

export async function renderTrendChart(accountId = null, year = null) {
  const ctx = document.getElementById('trendChart');
  if (!ctx) return;

  const wrap = ctx.closest('.chart-wrap');

  let data;
  try {
    const params = new URLSearchParams({ months: 12 });
    if (accountId != null) params.set('account_id', accountId);
    if (year) params.set('year', year);
    data = await apiFetch(`/api/reports/trends?${params}`);
  } catch {
    data = null;
  }

  if (!data || !data.months || !data.months.length || !data.series || !data.series.length) {
    if (trendChartInst) { trendChartInst.destroy(); trendChartInst = null; }
    ctx.style.display = 'none';
    let empty = wrap && wrap.querySelector('.chart-empty');
    if (!empty && wrap) {
      empty = document.createElement('div');
      empty.className = 'chart-empty';
      empty.textContent = 'Keine Trenddaten verfügbar';
      wrap.appendChild(empty);
    }
    return;
  }

  // Remove empty state if present
  const existing = wrap && wrap.querySelector('.chart-empty');
  if (existing) existing.remove();
  ctx.style.display = '';

  const FALLBACK_PALETTE = ['#c9a84c','#e05a6a','#b07ef8','#4d9de0','#3dcf8e','#f87686','#30c9e8','#a8d94a'];
  const monthNames = ['Jan','Feb','Mär','Apr','Mai','Jun','Jul','Aug','Sep','Okt','Nov','Dez'];

  // Trailing-Monate ohne Daten abschneiden
  let lastDataIdx = data.months.length - 1;
  while (lastDataIdx > 0 && data.series.every(s => (s.values[lastDataIdx] || 0) === 0)) {
    lastDataIdx--;
  }
  const trimmedMonths = data.months.slice(0, lastDataIdx + 1);
  const labels = trimmedMonths.map(m => {
    const [y, mo] = m.split('-');
    return `${monthNames[parseInt(mo) - 1]} ${y.slice(2)}`;
  });

  const TOP_N = 5;
  const topSeries = data.series
    .map(s => ({ ...s, total: s.values.reduce((a, b) => a + b, 0) }))
    .sort((a, b) => b.total - a.total)
    .slice(0, TOP_N);

  const datasets = topSeries.map((s, i) => {
    const color = CAT_COLORS[s.category] || FALLBACK_PALETTE[i % FALLBACK_PALETTE.length];
    return {
      label: s.category,
      data: s.values.slice(0, lastDataIdx + 1),
      borderColor: color,
      backgroundColor: 'transparent',
      borderWidth: 1.5,
      pointRadius: 0,
      pointHoverRadius: 4,
      pointBackgroundColor: color,
      tension: 0.3,
    };
  });

  if (trendChartInst) trendChartInst.destroy();
  trendChartInst = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: 'bottom',
          labels: { color: '#5a647a', font: { family: 'IBM Plex Mono', size: 10 }, boxWidth: 8, padding: 14 },
        },
        tooltip: {
          ...tooltipPlugin(),
          callbacks: { label: ctx => ` ${ctx.dataset.label}: ${fmtEur(ctx.parsed.y)}` },
        },
      },
      scales: {
        x: { ...axisStyle(), grid: { display: false } },
        y: { ...axisStyle(), ticks: { ...axisStyle().ticks, callback: v => v + '€' } },
      },
    },
  });
}

export function renderEtfForecastChart(aggregate) {
  const ctx = document.getElementById('etfForecastChart');
  if (!ctx) return;

  const years = [0, 1, 2, 3, 4, 5];
  const currentVal = aggregate.current_value;
  const sc = aggregate.scenarios;

  const mkData = (key) => [currentVal, ...sc[key]];

  if (etfForecastInst) etfForecastInst.destroy();
  etfForecastInst = new Chart(ctx, {
    type: 'line',
    data: {
      labels: ['Heute', 'Jahr 1', 'Jahr 2', 'Jahr 3', 'Jahr 4', 'Jahr 5'],
      datasets: [
        {
          label: 'Best (10%)',
          data: mkData('best'),
          borderColor: '#3dcf8e',
          backgroundColor: 'rgba(61,207,142,0.08)',
          borderWidth: 2,
          borderDash: [6, 3],
          pointRadius: 3,
          pointBackgroundColor: '#3dcf8e',
          tension: 0.2,
          fill: false,
        },
        {
          label: 'Casual (7%)',
          data: mkData('casual'),
          borderColor: '#4d9de0',
          backgroundColor: 'rgba(77,157,224,0.08)',
          borderWidth: 2.5,
          pointRadius: 4,
          pointBackgroundColor: '#4d9de0',
          tension: 0.2,
          fill: false,
        },
        {
          label: 'Worst (3%)',
          data: mkData('worst'),
          borderColor: '#e05a6a',
          backgroundColor: 'rgba(224,90,106,0.06)',
          borderWidth: 2,
          borderDash: [6, 3],
          pointRadius: 3,
          pointBackgroundColor: '#e05a6a',
          tension: 0.2,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: 'bottom',
          labels: { color: '#5a647a', font: { family: 'IBM Plex Mono', size: 10 }, boxWidth: 8, padding: 14 },
        },
        tooltip: {
          ...tooltipPlugin(),
          callbacks: { label: ctx => ` ${ctx.dataset.label}: ${fmtEur(ctx.parsed.y)}` },
        },
      },
      scales: {
        x: { ...axisStyle(), grid: { display: false } },
        y: { ...axisStyle(), ticks: { ...axisStyle().ticks, callback: v => {
          if (v >= 1000) return (v / 1000).toFixed(0) + 'k €';
          return v + '€';
        }}},
      },
    },
  });
}

export function renderEtfHistoryChart(purchases, positions) {
  const ctx = document.getElementById('etfHistoryChart');
  if (!ctx) return;

  // Cumulativer invested-Verlauf
  const sorted = [...purchases].sort((a, b) => a.date.localeCompare(b.date));
  const labels  = [];
  const invested = [];
  let running = 0;

  sorted.forEach(p => {
    running += p.total_eur;
    labels.push(p.date.slice(0, 7));
    invested.push(parseFloat(running.toFixed(2)));
  });

  if (etfHistoryInst) etfHistoryInst.destroy();
  etfHistoryInst = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Kumuliert investiert',
        data: invested,
        borderColor: '#4d9de0',
        backgroundColor: 'rgba(77,157,224,0.08)',
        borderWidth: 2,
        pointRadius: 3,
        fill: true,
        tension: 0.2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          ...tooltipPlugin(),
          callbacks: { label: ctx => ` Investiert: ${fmtEur(ctx.parsed.y)}` },
        },
      },
      scales: {
        x: { ...axisStyle(), grid: { display: false } },
        y: { ...axisStyle(), ticks: { ...axisStyle().ticks, callback: v => v + '€' } },
      },
    },
  });
}
