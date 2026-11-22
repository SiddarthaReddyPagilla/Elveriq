/* Read-only integrity review. Avoid unsafe HTML injection from warehouse data. */
(() => {
  'use strict';
  const button = document.getElementById('integrity-audit-run');
  const target = document.getElementById('integrity-audit-results');
  if (!button || !target) return;
  const escapeText = value => String(value ?? '').replace(/[&<>"']/g,
    ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  button.addEventListener('click', async () => {
    button.disabled = true;
    target.textContent = 'Checking the current warehouse ledger…';
    try {
      const response = await fetch('/api/reports/integrity-audit', {credentials:'same-origin'});
      if (!response.ok) throw new Error('Integrity scan unavailable (HTTP ' + response.status + ')');
      const data = await response.json();
      target.innerHTML = '<p><strong>' + data.checked_rules + ' rules checked · ' +
        data.failed_rules + ' need review</strong></p>' +
        '<table><thead><tr><th>Rule</th><th>Severity</th><th>Records</th><th>Sample IDs</th></tr></thead><tbody>' +
        data.checks.map(row => '<tr><td>' + escapeText(row.rule) + '</td><td>' +
          escapeText(row.severity) + '</td><td>' + escapeText(row.affected_records) + '</td><td>' +
          escapeText(row.sample_ids.join(', ')) + '</td></tr>').join('') + '</tbody></table>' +
        '<p class="muted">Results are a snapshot, not a physical count or automatic repair.</p>';
    } catch (error) { target.textContent = error.message; }
    finally { button.disabled = false; }
  });
})();
