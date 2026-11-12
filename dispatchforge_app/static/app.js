/* Elveriq demo dashboard. No credentials or API keys are stored in this file. */
(() => {
  const root = document.getElementById('workspace');
  if (!root) return;
  const demo = root.dataset.demo === 'true';
  const role = root.dataset.role;
  const suffix = demo ? '?demo=true' : '';
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  let inventory = [], products = [], warehouses = [], orders = [], purchases = [];

  if (role !== 'owner') document.querySelectorAll('.owner-only').forEach(el => el.remove());
  const byId = id => document.getElementById(id);
  const safe = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[ch]));
  const money = cents => '$' + (Number(cents) / 100).toFixed(2);
  const rowStatus = status => `<span class="status status-${safe(status)}">${safe(status)}</span>`;
  const table = (headers, rows) => rows.length
    ? `<table><thead><tr>${headers.map(h => `<th>${safe(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table>`
    : '<div class="empty-state">No records yet. Add your first item to get started.</div>';
  function notice(message, error = false) {
    const element = byId('notice');
    element.textContent = message;
    element.className = `alert ${error ? 'error' : 'success'}`;
    element.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
  async function api(path, options = {}) {
    const response = await fetch(`/api${path}${options.method ? '' : suffix}`, {
      credentials: 'same-origin',
      ...options,
      headers: { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
                 'X-CSRF-Token': csrf, ...(options.headers || {}) }
    });
    let data;
    try { data = await response.json(); } catch { data = {error: 'Unexpected server response'}; }
    if (!response.ok) throw new Error(data.error || data.detail?.[0]?.msg || `Request failed (${response.status})`);
    return data;
  }
  async function load() {
    try {
      const [overview, stock, productRows, warehouseRows, orderRows, movementRows, supplierRows, purchaseRows, transfers, counts, returns, replenishment, team] = await Promise.all([
        api('/overview'), api('/inventory'), api('/products'), api('/warehouses'),
        api('/orders'), api('/movements'), api('/suppliers'), api('/purchase-orders'),
        api('/transfers'), api('/cycle-counts'), api('/returns'), api('/replenishment'),
        role === 'owner' && !demo ? api('/staff') : Promise.resolve([])
      ]);
      inventory = stock; products = productRows; warehouses = warehouseRows; orders = orderRows; purchases = purchaseRows;
      const ids = {'stat-products': overview.products, 'stat-warehouses': overview.warehouses,
        'stat-stock': overview.on_hand, 'stat-reserved': overview.reserved,
        'stat-orders': overview.open_orders, 'stat-low': overview.low_stock,
        'stat-available': overview.on_hand - overview.reserved};
      for (const [id, value] of Object.entries(ids)) byId(id).textContent = Number(value).toLocaleString();
      const lows = stock.filter(r => r.low_stock);
      byId('alert-count').textContent = `${lows.length} alerts`;
      byId('low-stock-list').innerHTML = table(['Product', 'Location', 'Available'], lows.slice(0, 8).map(x =>
        `<tr><td><strong>${safe(x.name)}</strong><small>${safe(x.sku)}</small></td><td>${safe(x.warehouse)}</td><td><span class="status status-low">${x.available}</span></td></tr>`));
      byId('inventory-count').textContent = `${stock.length} location records`;
      byId('inventory-table').innerHTML = table(['Product / SKU', 'Location', 'On hand', 'Reserved', 'Available', 'Reorder at'], stock.map(x =>
        `<tr><td><strong>${safe(x.name)}</strong><small>${safe(x.sku)} · ${money(x.price_cents)}</small></td><td>${safe(x.warehouse)}</td><td>${x.on_hand}</td><td>${x.reserved}</td><td><strong class="${x.low_stock ? 'low-text' : ''}">${x.available}</strong></td><td>${x.reorder_point}</td></tr>`));
      byId('orders-table').innerHTML = table(['Order', 'Customer', 'Items', 'Due', 'Status', ''], orderRows.map(o =>
        `<tr><td>#${o.id}</td><td><strong>${safe(o.customer_name)}</strong></td><td>${o.items.map(i => `${safe(i.sku)} × ${i.quantity}`).join('<br>')}</td><td>${safe(o.due_date)}</td><td>${rowStatus(o.status)}</td><td>${!demo ? `<a class="link-button" href="/api/orders/${o.id}/pick-list.csv">Pick list CSV</a> ` : ''}${!demo && o.status === 'reserved' ? `<button class="link-button" data-order="${o.id}" data-action="fulfill">Fulfill</button> <button class="link-button muted-link" data-order="${o.id}" data-action="cancel">Cancel</button>` : '—'}</td></tr>`));
      byId('movements-table').innerHTML = table(['Time', 'Product', 'Location', 'Action', 'On hand Δ', 'Reserved Δ'], movementRows.map(m =>
        `<tr><td>${safe(m.created_at.slice(0, 16).replace('T', ' '))}</td><td>${safe(m.sku)}</td><td>${safe(m.warehouse)}</td><td>${safe(m.kind)}</td><td>${m.on_hand_delta > 0 ? '+' : ''}${m.on_hand_delta}</td><td>${m.reserved_delta > 0 ? '+' : ''}${m.reserved_delta}</td></tr>`));
      byId('suppliers-table').innerHTML = table(['Supplier', 'Contact'], supplierRows.map(s =>
        `<tr><td><strong>${safe(s.name)}</strong></td><td>${safe(s.email || 'No contact provided')}</td></tr>`));
      byId('purchases-table').innerHTML = table(['Reference', 'Supplier', 'Warehouse', 'Items', 'Expected', 'Status', 'Action'], purchaseRows.map(po =>
        `<tr><td><strong>${safe(po.reference)}</strong></td><td>${safe(po.supplier)}</td><td>${safe(po.warehouse)}</td><td>${po.items.map(item =>
           `${safe(item.sku)}: ${item.received}/${item.ordered} received${!demo && item.outstanding > 0 && ['ordered', 'partial'].includes(po.status)
             ? ` <button class="link-button" data-purchase-receive="${po.id}" data-line="${item.line_id}" data-outstanding="${item.outstanding}">Receive</button>` : ''}`).join('<br>')}</td><td>${safe(po.expected_date || '—')}</td><td>${rowStatus(po.status)}</td><td>${!demo && ['ordered', 'partial'].includes(po.status)
          ? `<button class="link-button muted-link" data-purchase-cancel="${po.id}">Cancel</button>` : '—'}</td></tr>`));
      byId('transfers-table').innerHTML = table(['SKU', 'From', 'To', 'Units', 'When'], transfers.map(t =>
        `<tr><td>${safe(t.sku)}</td><td>${safe(t.source)}</td><td>${safe(t.destination)}</td><td>${t.quantity}</td><td>${safe(t.created_at.slice(0, 16))}</td></tr>`));
      byId('counts-table').innerHTML = table(['SKU', 'Warehouse', 'Expected', 'Counted', 'Status', 'Action'], counts.map(c =>
        `<tr><td>${safe(c.sku)}</td><td>${safe(c.warehouse)}</td><td>${c.expected_on_hand}</td><td>${c.counted_on_hand === null ? '—' : c.counted_on_hand}</td><td>${rowStatus(c.status)}</td><td>${!demo && role === 'owner' && c.status === 'open' ? `<button class="link-button" data-count-post="${c.id}">Reconcile</button> <button class="link-button muted-link" data-count-cancel="${c.id}">Cancel</button>` : '—'}</td></tr>`));
      byId('returns-table').innerHTML = table(['Reference', 'Order', 'SKU', 'Units', 'When'], returns.map(r =>
        `<tr><td>${safe(r.reference)}</td><td>#${r.order_id}</td><td>${safe(r.sku)}</td><td>${r.quantity}</td><td>${safe(r.created_at.slice(0, 16))}</td></tr>`));
      byId('replenishment-table').innerHTML = table(['Product', 'Location', 'Available', 'Open PO units', 'Suggested'], replenishment.map(r =>
        `<tr><td><strong>${safe(r.product)}</strong><small>${safe(r.sku)}</small></td><td>${safe(r.warehouse)}</td><td>${r.available}</td><td>${r.incoming}</td><td><strong>${r.suggested_quantity}</strong></td></tr>`));
      if (byId('staff-table')) byId('staff-table').innerHTML = table(['Email', 'Role', 'Action'], team.map(u =>
        `<tr><td>${safe(u.email)}</td><td>${rowStatus(u.role)}</td><td>${u.role === 'owner' ? '—' : `<button class="link-button" data-staff-id="${u.id}" data-role="${safe(u.role)}">Change role</button>`}</td></tr>`));
      document.querySelectorAll('.fulfilled-order-select').forEach(select => {
        select.innerHTML = orderRows.filter(o => o.status === 'fulfilled').map(o =>
          `<option value="${o.id}">#${o.id} · ${safe(o.customer_name)}</option>`).join('');
      });
      document.querySelectorAll('.supplier-select').forEach(select => {
        const old = select.value;
        select.innerHTML = supplierRows.map(s => `<option value="${s.id}">${safe(s.name)}</option>`).join('');
        if (supplierRows.some(s => String(s.id) === old)) select.value = old;
      });
      document.querySelectorAll('.warehouse-select').forEach(select => {
        const old = select.value;
        select.innerHTML = warehouses.map(w => `<option value="${w.id}">${safe(w.name)}</option>`).join('');
        if (warehouses.some(w => String(w.id) === old)) select.value = old;
      });
      document.querySelectorAll('.sku-select').forEach(select => {
        const old = select.value;
        select.innerHTML = products.map(p => `<option value="${safe(p.sku)}">${safe(p.name)} · ${safe(p.sku)}</option>`).join('');
        if (products.some(p => p.sku === old)) select.value = old;
      });
    } catch (error) { notice(error.message, true); }
  }
  async function submit(id, path, build) {
    const form = byId(id); if (!form) return;
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const data = new FormData(form);
      try {
        await api(path, {method: 'POST', body: JSON.stringify(build(data))});
        notice('Saved successfully. Your warehouse records are updated.');
        form.reset(); await load();
      } catch (error) { notice(error.message, true); }
    });
  }
  document.querySelectorAll('[data-section]').forEach(button => button.addEventListener('click', () => {
    document.querySelectorAll('[data-section]').forEach(b => b.classList.toggle('active', b === button));
    document.querySelectorAll('[data-view]').forEach(el => el.classList.toggle('hidden', el.dataset.view !== button.dataset.section));
  }));
  if (!demo) {
    submit('product-form', '/products', d => ({sku: d.get('sku'), name: d.get('name'),
      price_cents: Math.round(Number(d.get('price')) * 100), reorder_point: Number(d.get('reorder_point'))}));
    submit('receive-form', '/stock/receive', d => ({warehouse_id: Number(d.get('warehouse_id')), sku: d.get('sku'),
      quantity: Number(d.get('quantity')), note: d.get('note')}));
    submit('warehouse-form', '/warehouses', d => ({name: d.get('name'), city: d.get('city')}));
    submit('supplier-form', '/suppliers', d => ({name: d.get('name'), email: d.get('email')}));
    submit('purchase-form', '/purchase-orders', d => ({reference: d.get('reference'),
      supplier_id: Number(d.get('supplier_id')), warehouse_id: Number(d.get('warehouse_id')),
      expected_date: d.get('expected_date') || null,
      items: [{sku: d.get('sku'), quantity: Number(d.get('quantity'))}]}));
    submit('transfer-form', '/transfers', d => ({
      source_warehouse_id: Number(d.get('source_warehouse_id')),
      destination_warehouse_id: Number(d.get('destination_warehouse_id')),
      sku: d.get('sku'), quantity: Number(d.get('quantity')), note: d.get('note')}));
    submit('count-form', '/cycle-counts', d => ({warehouse_id: Number(d.get('warehouse_id')),
      sku: d.get('sku'), note: d.get('note')}));
    submit('return-form', '/returns', d => ({order_id: Number(d.get('order_id')),
      sku: d.get('sku'), quantity: Number(d.get('quantity')),
      reference: d.get('reference'), reason: d.get('reason')}));
    submit('order-form', '/orders', d => ({warehouse_id: Number(d.get('warehouse_id')),
      customer_name: d.get('customer_name'), due_date: d.get('due_date'),
      items: [{sku: d.get('sku'), quantity: Number(d.get('quantity'))}]}));
    const today = new Date();
    const localToday = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
    if (byId('due-date')) {byId('due-date').value = localToday; byId('due-date').min = localToday;}
    const importForm = byId('import-form');
    if (importForm) importForm.addEventListener('submit', async event => {
      event.preventDefault();
      try {
        const result = await api('/import/products', {method: 'POST', body: new FormData(importForm)});
        notice(`Imported ${result.created} products (${result.skipped} existing or repeated SKUs skipped).`);
        importForm.reset(); await load();
      } catch (error) { notice(error.message, true); }
    });
    byId('counts-table').addEventListener('click', async event => {
      const post = event.target.closest('[data-count-post]');
      const cancel = event.target.closest('[data-count-cancel]');
      if (!post && !cancel) return;
      try {
        if (post) {
          const answer = window.prompt('Enter the physically counted units (whole number):');
          if (answer === null) return;
          const quantity = Number(answer);
          if (!Number.isInteger(quantity) || quantity < 0) return notice('Count must be a nonnegative whole number.', true);
          if (!window.confirm(`Post cycle count #${post.dataset.countPost}? This adjusts inventory.`)) return;
          await api(`/cycle-counts/${post.dataset.countPost}/post`, {method:'POST',
            body:JSON.stringify({counted_on_hand:quantity})});
        } else {
          if (!window.confirm('Cancel this physical count?')) return;
          await api(`/cycle-counts/${cancel.dataset.countCancel}/cancel`, {method:'POST'});
        }
        notice('Cycle count updated.'); await load();
      } catch (error) { notice(error.message, true); }
    });
    const inviteForm = byId('invite-form');
    if (inviteForm) inviteForm.addEventListener('submit', async event => {
      event.preventDefault(); const data = new FormData(inviteForm);
      try {
        const invited = await api('/staff/invitations', {method:'POST', body:JSON.stringify({
          email:data.get('email'), role:data.get('role')})});
        const workspace = document.querySelector('.slug-code')?.textContent.trim() || '';
        const link = `${location.origin}/join#token=${encodeURIComponent(invited.token)}&workspace=${encodeURIComponent(workspace)}`;
        byId('invite-output').textContent = `Share securely (shown once): ${link}`;
        notice('Invitation created. Copy the one-time link below the invitation form.');
        inviteForm.reset(); await load();
      } catch(error) { notice(error.message,true); }
    });
    const staffTable = byId('staff-table');
    if (staffTable) staffTable.addEventListener('click', async event => {
      const btn=event.target.closest('[data-staff-id]'); if (!btn) return;
      const desired=window.prompt('New role: manager, staff, or disabled',btn.dataset.role);
      if (desired === null) return;
      if (!['manager','staff','disabled'].includes(desired)) return notice('Choose manager, staff, or disabled.',true);
      if (!window.confirm(`Set employee #${btn.dataset.staffId} to ${desired}?`)) return;
      try { await api(`/staff/${btn.dataset.staffId}/role`,{method:'PATCH',
        body:JSON.stringify({role:desired})}); notice('Team member updated.'); await load(); }
      catch(error) { notice(error.message,true); }
    });
    byId('purchases-table').addEventListener('click', async event => {
      const receive = event.target.closest('[data-purchase-receive]');
      const cancel = event.target.closest('[data-purchase-cancel]');
      if (!receive && !cancel) return;
      try {
        if (receive) {
          const max = Number(receive.dataset.outstanding);
          const answer = window.prompt(`How many units arrived? Outstanding: ${max}`, String(max));
          if (answer === null) return;
          const quantity = Number(answer);
          if (!Number.isInteger(quantity) || quantity < 1 || quantity > max) {
            return notice(`Enter a whole number between 1 and ${max}.`, true);
          }
          await api(`/purchase-orders/${receive.dataset.purchaseReceive}/receive`, {
            method: 'POST', body: JSON.stringify({line_id: Number(receive.dataset.line), quantity})});
          notice('Receipt saved and stock history updated.');
        } else {
          if (!window.confirm(`Cancel outstanding units on purchase order #${cancel.dataset.purchaseCancel}?`)) return;
          await api(`/purchase-orders/${cancel.dataset.purchaseCancel}/cancel`, {method: 'POST'});
          notice('Purchase order cancelled. Previously received stock remains in inventory.');
        }
        await load();
      } catch (error) { notice(error.message, true); }
    });
    byId('orders-table').addEventListener('click', async event => {
      const button = event.target.closest('[data-order]'); if (!button) return;
      if (!window.confirm(`Confirm: ${button.dataset.action} order #${button.dataset.order}?`)) return;
      try {
        await api(`/orders/${button.dataset.order}/${button.dataset.action}`, {method:'POST'});
        notice('Order updated and stock ledger reconciled.'); await load();
      } catch (error) { notice(error.message, true); }
    });
  }
  load();
})();
