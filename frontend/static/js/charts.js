// charts.js – Chart.js wrappers
import { CAT_COLORS, fmtEur } from './app.js';

let barChartInst    = null;
let donutChartInst  = null;
let trendChartInst  = null;
let etfHistoryInst  = null;

const CHART_DEFAULTS = {
  backgroundColor: '#1a1e28',
  borderColor: '#242836',
  titleColor: '#e8eaf0',
  bodyColor: '#9ca3af',
};

function tooltipPlugin() {
  return {
    backgroundColor: CHART_DEFAULTS.backgroundColor,
    borderColor: CHART_DEFAULTS.borderColor,
    borderWidth: 1,
    titleColor: CHART_DEFAULTS.titleColor,
    bodyColor: CHART_DEFAULTS.bodyColor,
    padding: 10,
  };
}

function axisStyle() {
  return {
    ticks: { color: '#6b7280', font: { family: 'DM Mono', size: 11 } },
    grid: { color: '#242836' },
    border: { color: '#242836' },
  };
}

export function initCharts() {
  Chart.defaults.color = '#6b7280';
  Chart.defaults.font.family = 'DM Mono';
}

export function renderBarChart(allSummary) {
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

  // Last 6 months
  const recent = allSummary.slice(-6);
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
          backgroundColor: '#f87171cc',
          borderRadius: 2,
        },
        {
          label: 'Einnahmen',
          data: recent.map(s => s.income),
          backgroundColor: '#4ade80cc',
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
          labels: { color: '#6b7280', font: { family: 'DM Mono', size: 10 }, boxWidth: 10, padding: 12 },
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

export async function renderTrendChart() {
  const ctx = document.getElementById('trendChart');
  if (!ctx) return;

  const wrap = ctx.closest('.chart-wrap');

  let data;
  try {
    data = await fetch('/api/reports/trends?months=6').then(r => {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    });
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

  const FALLBACK_PALETTE = ['#f0a500','#e05a7a','#c084fc','#3d9cf5','#34d399','#fb7185','#22d3ee','#a3e635'];
  const monthNames = ['Jan','Feb','Mär','Apr','Mai','Jun','Jul','Aug','Sep','Okt','Nov','Dez'];
  const labels = data.months.map(m => {
    const [, mo] = m.split('-');
    return monthNames[parseInt(mo) - 1];
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
      data: s.values,
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
          labels: { color: '#6b7280', font: { family: 'DM Mono', size: 10 }, boxWidth: 10, padding: 12 },
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
        borderColor: '#22d3ee',
        backgroundColor: 'rgba(34,211,238,0.08)',
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
