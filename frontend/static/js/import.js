// import.js – PDF Upload & Drag-Drop
import { apiFetch } from './app.js';

export function initImport(onImportDone, onHistoryLoad) {
  const zone      = document.getElementById('dropZone');
  const fileInput = document.getElementById('fileInput');
  const queue     = document.getElementById('importQueue');
  const resultBox = document.getElementById('importResult');
  const resultContent = document.getElementById('importResultContent');

  // Click to browse
  zone.addEventListener('click', () => fileInput.click());

  fileInput.addEventListener('change', () => {
    if (fileInput.files.length) processFiles(Array.from(fileInput.files));
    fileInput.value = '';
  });

  // Drag & drop
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const files = Array.from(e.dataTransfer.files).filter(f => f.name.toLowerCase().endsWith('.pdf'));
    if (files.length) processFiles(files);
  });

  async function processFiles(files) {
    resultBox.style.display = 'none';
    queue.innerHTML = '';

    const results = [];

    for (const file of files) {
      const item = document.createElement('div');
      item.className = 'import-item';
      const displayName = file.name.length > 30 ? file.name.slice(0, 30) + '…' : file.name;
      const nameEl = document.createElement('div');
      nameEl.className = 'import-item-name';
      nameEl.title = file.name;
      nameEl.textContent = '📄 ' + displayName;
      const statusEl = document.createElement('div');
      statusEl.className = 'import-item-status loading';
      statusEl.textContent = 'Wird verarbeitet…';
      item.appendChild(nameEl);
      item.appendChild(statusEl);
      queue.appendChild(item);

      try {
        const fd = new FormData();
        fd.append('file', file);
        const res = await apiFetch('/api/import/pdf', { method: 'POST', body: fd });
        statusEl.textContent = `✓ ${res.imported} importiert, ${res.skipped} übersprungen`;
        statusEl.className = 'import-item-status success';
        results.push({ file: file.name, ...res, ok: true });
      } catch(e) {
        statusEl.textContent = `✗ Fehler: ${e.message}`;
        statusEl.className = 'import-item-status error';
        results.push({ file: file.name, error: e.message, ok: false });
      }
    }

    // Summary
    const okResults     = results.filter(r => r.ok);
    const totalImported = okResults.reduce((s, r) => s + (r.imported || 0), 0);
    const totalEtf      = okResults.reduce((s, r) => s + (r.etf_purchases || 0), 0);
    const totalSkipped  = okResults.reduce((s, r) => s + (r.skipped || 0), 0);
    const failed        = results.filter(r => !r.ok).length;

    // Build stat tiles
    const stats = [
      { label: 'Transaktionen', value: totalImported, color: 'var(--green)',  icon: '✓' },
      { label: 'ETF-Käufe',     value: totalEtf,      color: 'var(--accent)', icon: '◈' },
      { label: 'Übersprungen',  value: totalSkipped,  color: 'var(--muted)',  icon: '↷' },
      { label: 'Fehler',        value: failed,        color: failed > 0 ? 'var(--red)' : 'var(--muted)', icon: failed > 0 ? '✗' : '–' },
    ];

    resultContent.textContent = '';
    const grid = document.createElement('div');
    grid.style.cssText = 'display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-top:0.5rem';
    stats.forEach(s => {
      const cell = document.createElement('div');
      const labelEl = document.createElement('div');
      labelEl.style.cssText = 'color:var(--muted);font-size:0.62rem;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.25rem';
      labelEl.textContent = s.label;
      const valWrap = document.createElement('div');
      valWrap.style.cssText = `font-size:1.4rem;font-family:'Syne',sans-serif;color:${s.color};display:flex;align-items:baseline;gap:0.3rem`;
      const iconEl = document.createElement('span');
      iconEl.style.cssText = 'font-size:0.85rem;opacity:0.7';
      iconEl.textContent = s.icon;
      const numEl = document.createElement('span');
      numEl.textContent = s.value;
      valWrap.appendChild(iconEl);
      valWrap.appendChild(numEl);
      cell.appendChild(labelEl);
      cell.appendChild(valWrap);
      grid.appendChild(cell);
    });
    resultContent.appendChild(grid);

    // Per-file account statement labels
    const labeled = okResults.filter(r => r.account_statement);
    if (labeled.length) {
      const labelList = document.createElement('div');
      labelList.style.cssText = 'margin-top:0.75rem;font-size:0.72rem;color:var(--muted)';
      labeled.forEach(r => {
        const row = document.createElement('div');
        row.textContent = `${r.file} → Auszug ${r.account_statement}`;
        labelList.appendChild(row);
      });
      resultContent.appendChild(labelList);
    }

    resultBox.style.display = 'block';

    if (totalImported > 0) {
      onImportDone();
      onHistoryLoad();
    }
  }
}
