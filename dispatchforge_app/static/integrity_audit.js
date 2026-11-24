/* Read-only integrity review. Avoid unsafe HTML injection from warehouse data. */
(() => {
  'use strict';
  const button = document.getElementById('integrity-audit-run');
  const target = document.getElementById('integrity-audit-results');
  const warehouse = document.getElementById('integrity-audit-warehouse');
  const severity = document.getElementById('integrity-audit-severity');
  const exportLink = document.getElementById('integrity-audit-export');
  if (!button || !target) return;
  const escapeText = value => String(value ?? '').replace(/[&<>"']/g,
    ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const scopedQuery = () => {
    const params = new URLSearchParams();
    if (warehouse && warehouse.value) params.set('warehouse_id', warehouse.value);
    if (severity && severity.value) params.set('severity', severity.value);
    return params.toString();
  };
  const syncExport = () => {
    const query = scopedQuery();
    if (exportLink) exportLink.href = '/api/reports/integrity-audit.csv' + (query ? '?' + query : '');
  };
  warehouse?.addEventListener('change', syncExport);
  severity?.addEventListener('change', syncExport);
  fetch('/api/warehouses', {credentials:'same-origin'}).then(response => {
    if (!response.ok) throw new Error('Unable to load warehouses');
    return response.json();
  }).then(rows => {
    if (!Array.isArray(rows) || !warehouse) return;
    rows.forEach(row => {
      const option = document.createElement('option');
      option.value = String(row.id);
      option.textContent = row.name || 'Warehouse ' + row.id;
      warehouse.appendChild(option);
    });
  }).catch(() => { if (warehouse) warehouse.title = 'Warehouse filter unavailable'; });
  button.addEventListener('click', async () => {
    button.disabled = true;
    target.textContent = 'Checking the current warehouse ledger…';
    try {
      syncExport();
      const query = scopedQuery();
      const response = await fetch('/api/reports/integrity-audit' + (query ? '?' + query : ''), {credentials:'same-origin'});
      if (!response.ok) throw new Error('Integrity scan unavailable (HTTP ' + response.status + ')');
      const data = await response.json();
      target.innerHTML = '<p><strong>' + data.checked_rules + ' rules checked · ' +
        data.failed_rules + ' need review</strong></p>' +
        '<p>Critical records: ' + escapeText(data.severity_totals.critical.affected_records) +
        ' · Warning records: ' + escapeText(data.severity_totals.warning.affected_records) + '</p>' +
        '<table><thead><tr><th>Rule</th><th>Severity</th><th>Records</th><th>Sample IDs</th></tr></thead><tbody>' +
        data.checks.map(row => '<tr><td>' + escapeText(row.rule) + '</td><td>' +
          escapeText(row.severity) + '</td><td>' + escapeText(row.affected_records) + '</td><td>' +
          escapeText(row.sample_ids.join(', ')) + '</td></tr>').join('') + '</tbody></table>' +
        '<p class="muted">Results are a snapshot, not a physical count or automatic repair.</p>';
    } catch (error) { target.textContent = error.message; }
    finally { button.disabled = false; }
  });
})();
